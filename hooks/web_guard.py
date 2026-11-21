#!/usr/bin/env python3
"""Web search budget (PreToolUse hook, matcher WebSearch).

Claude Code's WebSearch is the costliest tool on web work, and not because of the results: each search is a separate
model request that re-sends the conversation as uncached input, plus a per-search fee (~$0.07 a search on Sonnet; on
THOL's web-research task, ~45% of the run). So this hook avoids running it:
1. A query that repeats an earlier one (>= 80% of its content words) is blocked: its results are already above.
2. Otherwise the hook runs the search itself on public search engines (DuckDuckGo, Brave, Bing, Marginalia, Mojeek,
   Yahoo; in parallel, 8 s budget, each engine benched for 10 minutes after it throttles us) and hands Claude the
   merged hits as the block reason, which Claude reads as the search result. Off-topic pages are dropped.
3. If that finds too little, the native WebSearch runs, up to LEAN_WEB_SEARCHES native searches a session (default
   15; 0 = no cap); past that Claude is told to WebFetch pages it already found, or finish.
LEAN_WEB_SEARCH=0 turns step 2 off. Any hook error lets the native search run."""
import base64
import html as htmlmod
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from itertools import zip_longest

CAP = int(os.environ.get("LEAN_WEB_SEARCHES", 15))
OWN = os.environ.get("LEAN_WEB_SEARCH", "1") != "0"
MARK = "[Claude Lean search]"
BUDGET, MAX_HITS, MIN_HITS, BENCH = 8.0, 15, 3, 600
STATE = os.path.join(tempfile.gettempdir(), "claude-lean-engines.json")

STOP = set("a an and the of for to in on with by or vs site com org github open source opensource project projects "
           "repo repository tool tools library official llm llms ai 2023 2024 2025 2026 2027 best list".split())

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
           "Sec-Fetch-Site": "none", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-User": "?1", "Sec-Fetch-Dest": "document",
           "Upgrade-Insecure-Requests": "1", "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
           "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"'}


# ---------- repeats and the native-search count, from the transcript ----------

def words(q):
    return set(re.findall(r"[a-z0-9]+", q.lower())) - STOP


def same(a, b):
    """Near-repeat: >= 80% of the content words shared (Jaccard), ignoring filler like "open source GitHub 2025"."""
    return bool(a and b) and len(a & b) / len(a | b) >= 0.8


def history(transcript):
    """[(query, served_by_us)] for every WebSearch so far in this session."""
    calls, results = {}, {}
    try:
        with open(transcript, encoding="utf-8", errors="replace") as f:
            for line in f:
                if "WebSearch" not in line and MARK not in line:
                    continue
                try:
                    content = json.loads(line)["message"]["content"]
                except (ValueError, KeyError, TypeError):
                    continue
                for b in content if isinstance(content, list) else []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use" and b.get("name") == "WebSearch":
                        calls.setdefault(b.get("id"), (b.get("input") or {}).get("query", ""))
                    elif b.get("type") == "tool_result":
                        results[b.get("tool_use_id")] = MARK in json.dumps(b.get("content"))
    except OSError:
        pass
    return [(q, results.get(i, False)) for i, q in calls.items()]


# ---------- our own search ----------

def clean(s):
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def ddg(page):
    out = []
    for m in re.finditer(r'(?is)<a\b[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page):
        href = htmlmod.unescape(m.group(1))
        if "uddg=" in href:
            href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
        elif href.startswith("//"):
            href = "https:" + href
        s = re.search(r'(?is)result__snippet[^>]*>(.*?)</a>', page[m.end():m.end() + 2048])
        out.append((clean(m.group(2)), href, clean(s.group(1)) if s else ""))
    return out


def blocks(page, marker):
    starts = [m.start() for m in re.finditer(re.escape(marker), page)]
    return [page[a:b] for a, b in zip(starts, starts[1:] + [len(page)])]


def bing(page):
    out = []
    for blk in blocks(page, 'class="b_algo"'):
        m = re.search(r'(?is)<h2[^>]*>\s*<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk)
        if not m:
            continue
        href = htmlmod.unescape(m.group(1))
        u = re.search(r"[?&]u=a1([^&]+)", href)
        if u:
            try:
                href = base64.urlsafe_b64decode(u.group(1) + "=" * (-len(u.group(1)) % 4)).decode()
            except ValueError:
                pass
        s = re.search(r'(?is)class="b_caption.*?<p[^>]*>(.*?)</p>', blk)
        out.append((clean(m.group(2)), href, clean(s.group(1)) if s else ""))
    return out


def brave(page):
    out = []
    for blk in blocks(page, 'data-type="web"'):
        blk = blk[:20000]
        u = re.search(r'<a href="(https?://[^"]+)"', blk)
        t = re.search(r'(?is)class="title[^"]*"[^>]*title="([^"]+)"', blk) or re.search(
            r'(?is)class="title[^"]*"[^>]*>(.*?)</div>', blk)
        s = re.search(r'(?is)class="generic-snippet.*?class="content[^"]*"[^>]*>(.*?)</div>', blk)
        if u and t:
            out.append((clean(t.group(1)), htmlmod.unescape(u.group(1)), clean(s.group(1)) if s else ""))
    return out


def marginalia(page):
    out = []
    for blk in blocks(page, 'class="card search-result"'):
        m = re.search(r'(?is)<a[^>]*class="title"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk)
        s = re.search(r'(?is)<p[^>]*class="description"[^>]*>(.*?)</p>', blk)
        if m:
            out.append((clean(m.group(2)), htmlmod.unescape(m.group(1)), clean(s.group(1)) if s else ""))
    return out


def mojeek(page):
    out = []
    for m in re.finditer(r'(?is)<a[^>]*class="title"[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', page):
        s = re.search(r'(?is)<p class="s">(.*?)</p>', page[m.end():m.end() + 2048])
        out.append((clean(m.group(2)), htmlmod.unescape(m.group(1)), clean(s.group(1)) if s else ""))
    return out


def yahoo(page):
    out = []
    for blk in blocks(page, 'class="algo-sr'):
        m = re.search(r'(?is)<a\b[^>]*href="(https://[^"]*?/RU=([^/"]+)/R[SK]=[^"]*)"[^>]*>(.*?)</a>', blk)
        s = re.search(r'(?is)class="compText[^"]*"[^>]*>(.*?)</div>', blk)
        if m:
            out.append((clean(re.sub(r"(?is)<span.*?</span>", "", m.group(3))), urllib.parse.unquote(m.group(2)),
                        clean(s.group(1)) if s else ""))
    return out


ENGINES = {  # name: (url template, cookie, parser)
    "duckduckgo": ("https://html.duckduckgo.com/html/?q={q}", None, ddg),
    "brave": ("https://search.brave.com/search?q={q}&source=web", None, brave),
    "bing": ("https://www.bing.com/search?q={q}", None, bing),
    "marginalia": ("https://old-search.marginalia.nu/search?query={q}", None, marginalia),
    "mojeek": ("https://www.mojeek.com/search?q={q}", None, mojeek),
    "yahoo": ("https://search.yahoo.com/search?p={q}&iscqry=&pz=7&bct=0&xargs=0",
              "sB=v=1&vm=p&fl=1&vl=lang_en&pn=10&rw=new&userset=1", yahoo),
}


def on_topic(hit, needles):
    hay = " ".join(hit).lower()
    return sum(n in hay for n in needles) >= min(2, len(needles))


def run_engine(name, query, needles):
    url, cookie, parse = ENGINES[name]
    h = dict(HEADERS, **({"Cookie": cookie} if cookie else {}))
    req = urllib.request.Request(url.format(q=urllib.parse.quote_plus(query)), headers=h)
    with urllib.request.urlopen(req, timeout=BUDGET - 1) as r:
        page = r.read(4_000_000).decode("utf-8", "replace")
    hits = [x for x in parse(page) if x[1].startswith("http") and 3 <= len(x[0]) <= 300]
    good = [x for x in hits if on_topic(x, needles)] if needles else hits
    if len(good) < MIN_HITS:                   # challenge page, decoy results, or a thin answer: bench the engine
        raise ValueError(f"{len(hits)} hits, {len(good)} on topic")
    return good


def own_search(query, blocked_domains):
    try:
        with open(STATE) as f:
            bench = json.load(f)
    except (OSError, ValueError):
        bench = {}
    now = time.time()
    names = [n for n in ENGINES if bench.get(n, 0) < now]
    needles = [w[:6] for w in words(query) if len(w) >= 4]
    if not names:
        return []
    pool = ThreadPoolExecutor(len(names))
    futs = {pool.submit(run_engine, n, query, needles): n for n in names}
    done, _ = wait(futs, timeout=BUDGET)
    lists = []
    for f, n in futs.items():
        if f in done and not f.exception():
            lists.append(f.result())
        elif f in done:
            bench[n] = now + BENCH
    pool.shutdown(wait=False, cancel_futures=True)
    try:
        with open(STATE, "w") as f:
            json.dump(bench, f)
    except OSError:
        pass
    seen, merged = set(), []
    for row in zip_longest(*lists):
        for hit in row:                        # interleave engines: rank 1 of each, then rank 2, ...
            if not hit:
                continue
            key = hit[1].split("#")[0].rstrip("/").lower()
            host = urllib.parse.urlsplit(hit[1]).hostname or ""
            if key in seen or any(host == d or host.endswith("." + d) for d in blocked_domains):
                continue
            seen.add(key)
            merged.append(hit)
    return merged[:MAX_HITS]


# ---------- hook ----------

def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def main():
    d = json.load(sys.stdin)
    ti = d.get("tool_input") or {}
    q = ti.get("query") or ""
    past = history(d.get("transcript_path") or "")
    w = words(q)
    for p, _ in past:
        if same(w, words(p)):
            return deny(f'Claude Lean: this repeats your earlier search "{p}"; its results are above. Search a '
                        "different angle, or WebFetch a page you already found.")
    if OWN and q and not ti.get("allowed_domains"):
        hits = own_search(q, ti.get("blocked_domains") or [])
        if len(hits) >= MIN_HITS:
            lines = [f'{MARK} Web search results for "{q}" (fetched by the Claude Lean hook instead of the WebSearch '
                     "tool; treat them as this search's results and WebFetch a URL for details):"]
            for i, (t, u, s) in enumerate(hits, 1):
                lines.append(f"{i}. {t}\n   {u}" + (f"\n   {s[:240]}" if s else ""))
            return deny("\n".join(lines))
    native = sum(1 for _, ours in past if not ours)
    if CAP and native >= CAP:
        deny(f"Claude Lean: {native} web searches this session (~$0.07 each; a WebFetch is ~$0.015). Use WebFetch on "
             "the pages you already found (awesome-lists, topic pages, registries, docs indexes), or finish with what "
             "you have. To allow more, set LEAN_WEB_SEARCHES.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
