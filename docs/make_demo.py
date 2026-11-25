#!/usr/bin/env python3
"""Render docs/demo.gif (needs Pillow and DejaVu Sans Mono).

    python3 docs/make_demo.py

The install scene is captured live (install.sh into a throwaway config dir). The request counts and the benchmark come
from the README's measured tables."""
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
W, H, PAD, LH, FS = 1000, 560, 22, 21, 15
F = ImageFont.truetype(FONT, FS)
FB = ImageFont.truetype(FONT.replace(".ttf", "-Bold.ttf"), FS)
BIG = ImageFont.truetype(FONT.replace(".ttf", "-Bold.ttf"), 30)
BG, BAR, FG, DIM, GRN, RED, ACC = "#14161b", "#1f2229", "#d6d9df", "#7d8590", "#7ee787", "#ff7b72", "#d97757"
DOTS = ("#ff5f57", "#febc2e", "#28c840")


def capture():
    with tempfile.TemporaryDirectory() as t:
        out = subprocess.run(["bash", str(ROOT / "install.sh")], env={**os.environ, "CLAUDE_CONFIG_DIR": t},
                             capture_output=True, text=True, check=True).stdout
        out = out.replace(t, "~/.claude")
    line = out.strip().split("\n")[-1] if "note:" not in out else out.strip().split("\n")[0]
    head, _, added = line.partition(" (+ ")
    return [head] + [f"  + {a}" for a in added.rstrip(")").split(", ") if a]


def color(line):
    if "Claude Lean" in line and not line.startswith("$"):
        return ACC
    if line.startswith("  + ") or "-53%" in line or "-24%" in line:
        return GRN
    if line.startswith("  "):
        return DIM
    return FG


def render(lines, title, cursor=False):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 34], fill=BAR)
    for i, c in enumerate(DOTS):
        d.ellipse([16 + i * 22, 11, 28 + i * 22, 23], fill=c)
    d.text((W // 2, 17), title, font=F, fill=DIM, anchor="mm")
    vis = lines[-((H - 50) // LH):]
    for i, ln in enumerate(vis):
        y = 46 + i * LH
        if ln.startswith("$ "):
            d.text((PAD, y), "$", font=FB, fill=ACC)
            d.text((PAD + 18, y), ln[2:], font=FB, fill=FG)
        else:
            d.text((PAD, y), ln, font=F, fill=color(ln))
    if cursor:
        last = vis[-1] if vis else ""
        x = PAD + (18 + F.getlength(last[2:]) if last.startswith("$ ") else F.getlength(last))
        y = 46 + (len(vis) - 1) * LH
        d.rectangle([x + 2, y, x + 10, y + 17], fill=FG)
    return im


class Movie:
    def __init__(self):
        self.frames, self.durs = [], []

    def add(self, im, ms):
        self.frames.append(im)
        self.durs.append(ms)

    def typed(self, lines, cmd, title):
        for i in range(0, len(cmd) + 1, 2):
            self.add(render(lines + ["$ " + cmd[:i]], title, True), 45)
        self.add(render(lines + ["$ " + cmd], title, True), 350)
        return lines + ["$ " + cmd]

    def out(self, lines, new, title, ms=40, hold=1800):
        for i in range(len(new)):
            self.add(render(lines + new[:i + 1], title), ms)
        self.add(render(lines + new, title), hold)
        return lines + new

    def card(self, big, small, hold):
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        d.text((W // 2, H // 2 - 40), big, font=BIG, fill=FG, anchor="mm")
        for i, s in enumerate(small):
            d.text((W // 2, H // 2 + 16 + i * 28), s, font=F, fill=(ACC if i == 0 else DIM), anchor="mm")
        self.add(im, hold)

    def save(self, path):
        def rgb(h):
            return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
        cols = []                       # one explicit palette: every text color blended into both backgrounds
        for base in (BG, BAR):
            for c in (FG, DIM, GRN, RED, ACC, *DOTS):
                for t in range(8):
                    cols.append(tuple(round(x + (y - x) * t / 7) for x, y in zip(rgb(base), rgb(c))))
        cols = list(dict.fromkeys(cols))[:256]
        ref = Image.new("P", (1, 1))
        ref.putpalette([v for c in cols for v in c] + [0] * (768 - 3 * len(cols)))
        pal = [f.quantize(palette=ref, dither=Image.NONE) for f in self.frames]
        pal[0].save(path, save_all=True, append_images=pal[1:], duration=self.durs, loop=0, optimize=True, disposal=1)


def main():
    m = Movie()
    m.card("Claude Lean", ["Claude Code, about 20% cheaper and 24% faster. Same tasks solved.",
                       "No new instructions for Claude: only switches off what you pay for and don't use."], 2800)
    t = "~: bash"
    L = m.typed([], "./install.sh", t)
    m.out(L, capture(), t, ms=120, hold=2600)

    t = "3-prompt Claude Code chat, every request logged"
    L = m.typed([], "requests sent", t)
    m.out(L, ["", "  plain Claude Code   7 requests   ~85K tokens",
              "    3 answers + 2 next-prompt suggestions (whole chat each) + title + quota check",
              "", "  Claude Lean         4 requests   ~40K tokens   (-53%)",
              "    3 answers + quota check, same answers"], t, ms=300, hold=3400)

    t = "SWE-bench Verified: 33 real GitHub issues, official grader"
    L = m.typed([], "results", t)
    m.out(L, ["", "                      solved    cost      time",
              "  plain Claude Code   20 / 33   $24.78    135 min",
              "  Claude Lean         20 / 33   $22.65    103 min (-24%)"], t, ms=300, hold=3600)

    m.card("Same tasks solved. Lower bill.", ["./install.sh", "./install.sh --uninstall removes everything it added"], 3000)
    (ROOT / "docs").mkdir(exist_ok=True)
    m.save(ROOT / "docs" / "demo.gif")
    print(f"{len(m.frames)} frames, {sum(m.durs) / 1000:.1f}s")


if __name__ == "__main__":
    main()
