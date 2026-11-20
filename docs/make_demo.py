#!/usr/bin/env python3
"""Render docs/demo.gif from real claude-lean output (needs Pillow and DejaVu Sans Mono).

    python3 docs/make_demo.py

Every terminal frame is captured live: `init` runs into a throwaway folder and the pytest scene runs tools/squeeze.py on
a generated 400-test log. The numbers on the cards come from the README's benchmark tables."""
import os
import subprocess
import sys
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
        env = {**os.environ, "LEAN_HOME": f"{t}/lean", "CLAUDE_DIR": f"{t}/claude", "LEAN_CACHE": f"{t}/cache"}
        init = subprocess.run(["node", str(ROOT / "bin" / "cli.js"), "init"], env=env, capture_output=True, text=True).stdout
        init = init.replace(f"{t}/lean", "~/.claude-lean").replace(f"{t}/claude", "~/.claude")
        log = ["============================= test session starts ==============================",
               "platform linux -- Python 3.12.3, pytest-8.3.4", "collected 400 items", ""]
        log += [f"tests/test_shop.py::test_case_{i} PASSED{'':>30}[{i * 100 // 400:>3}%]" for i in range(399)]
        log += ["tests/test_shop.py::test_parse_price FAILED                              [100%]", "",
                "=================================== FAILURES ===================================",
                "______________________________ test_parse_price _______________________________", "",
                "    def test_parse_price():", ">       assert parse_price('$1,234.50') == 1234.5",
                "E       AssertionError: assert 1.0 == 1234.5", "", "tests/test_shop.py:41: AssertionError",
                "=========================== short test summary info ============================",
                "FAILED tests/test_shop.py::test_parse_price - AssertionError: assert 1.0 == 1234.5",
                "======================== 1 failed, 399 passed in 2.31s ========================="]
        trim = subprocess.run([sys.executable, str(ROOT / "tools" / "squeeze.py"), "filter", "pytest"], env=env,
                              input="\n".join(log) + "\n", capture_output=True, text=True).stdout
        trim = trim.replace(str(ROOT / "tools"), "~/.claude-lean/tools")
    return init.rstrip("\n").split("\n"), trim.rstrip("\n").split("\n")


def color(line):
    if "Claude Lean" in line or "squeeze.py get" in line:
        return ACC
    if "FAILED" in line or line.startswith("E ") or "Error" in line:
        return RED
    if line.startswith(("hook", "env", "allow", "wrote", "copy", "copied")):
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

    def out(self, lines, new, title, step=1, ms=40, hold=1800):
        new = [w for ln in new for w in ([ln[i:i + 100] for i in range(0, len(ln), 100)] or [""])]
        for i in range(0, len(new), step):
            self.add(render(lines + new[:i + step], title), ms)
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
    init, trim = capture()
    m = Movie()
    m.card("Claude Lean", ["Short Claude Code tasks cost 32-74% less, same pass rate.",
                           "Free. Local. Open source. No telemetry."], 2400)
    t = "~/shop: bash"
    L = m.typed([], "npx claude-lean init", t)
    m.out(L, init, t, ms=60, hold=2200)

    t = "Claude Code: Bash tool output"
    noisy = [f"tests/test_shop.py::test_case_{i} PASSED{'':>30}[{i * 100 // 400:>3}%]" for i in range(0, 399, 7)]
    L = m.typed([], "pytest", t)
    L = m.out(L, ["collected 400 items"] + noisy, t, step=3, ms=30, hold=300)
    m.out(L, ["", "  ... 416 lines, and every later request in this session carries them"], t, hold=1400)
    L = m.typed([], "pytest      # with Claude Lean", t)
    m.out(L, trim, t, ms=70, hold=3200)

    t = "~/shop: bash"
    L = m.typed([], "npx claude-lean lite    # quick jobs: core tools only", t)
    m.out(L, ["", "  tokens sent before you type anything (clean install, Claude Code 2.1.239)",
              "  plain Claude Code   17,243",
              "  claude-lean lite     5,442   (-68%)"], t, ms=250, hold=3000)

    m.card("$0.0081  ->  $0.0021", ["One short task on Haiku 5.5 with claude-lean lite: 74% cheaper, 15/15 passed in both.",
                                    "npx claude-lean init"], 3400)
    m.save(ROOT / "docs" / "demo.gif")
    print(f"{len(m.frames)} frames, {sum(m.durs) / 1000:.1f}s")


if __name__ == "__main__":
    main()
