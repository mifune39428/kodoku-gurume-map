#!/usr/bin/env python3
"""公式（テレビ東京）が YouTube に上げている各話の PR 動画を話数に紐づける。

本編の静止画をこちらのサイトに複製するのは権利的にできないので、
公式が公開している動画を YouTube の埋め込みで見せるための下ごしらえ。
各話ページに1本ずつ埋まっているシーズンと、
全話が1ページに載っていて「第N話」の見出しごとに埋まっているシーズンがある。
"""
import html as htmllib
import json
import os
import re
import subprocess
import sys

BASE = "https://www.tv-tokyo.co.jp"
CACHE = "off/o"
os.makedirs(CACHE, exist_ok=True)
YT = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=)|youtu\.be/)([A-Za-z0-9_\-]{11})")

official = json.load(open("official_map.json"))


def fetch(url):
    key = re.sub(r"[^A-Za-z0-9]+", "_", url)[-110:]
    path = os.path.join(CACHE, key + ".html")
    if not os.path.exists(path):
        subprocess.run(["curl", "-sL", "--max-time", "25", "-A", "Mozilla/5.0",
                        url, "-o", path], check=False)
    try:
        raw = open(path, "rb").read()
    except OSError:
        return ""
    m = re.search(rb"charset=[\"']?([\w-]+)", raw[:2000], re.I)
    enc = (m.group(1).decode("ascii", "ignore") if m else "utf-8").lower()
    enc = {"shift_jis": "cp932", "shift-jis": "cp932", "sjis": "cp932"}.get(enc, enc)
    for c in (enc, "utf-8", "cp932"):
        try:
            return raw.decode(c)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


ZEN = str.maketrans("０１２３４５６７８９", "0123456789")
videos = {}   # "Season N" -> {ep: youtube id}

# 1) 各話ページが独立しているシーズン: そのページの動画がその話のもの
for season, eps in official["episodes"].items():
    got = {}
    for ep, url in eps.items():
        ids = YT.findall(fetch(url))
        if len(ids) == 1:              # 複数あるページは他話の予告も混ざっているので採らない
            got[int(ep)] = ids[0]
    if got:
        videos[season] = got

# 2) 全話が1ページのシーズン: 「第N話」の見出しごとに近い動画を拾う
for season in ("Season 10", "Season 11"):
    page = fetch(official["index"][season])
    marks = [(m.start(), int(m.group(1)))
             for m in re.finditer(r"第\s*([0-9０-９]{1,2})\s*話", page.translate(ZEN))]
    got = videos.setdefault(season, {})
    for i, (pos, ep) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(page)
        ids = YT.findall(page[pos:end])
        if ids and ep not in got:
            got[ep] = ids[0]
    if not got:
        videos.pop(season, None)

# 3) スペシャルの特設サイト
sp = {}
for season, url in official["sp"].items():
    ids = YT.findall(fetch(url))
    if ids:
        sp[season] = ids[0]

out = {"episodes": {k: {str(e): v for e, v in sorted(v.items())} for k, v in videos.items()},
       "sp": sp}
json.dump(out, open("video_map.json", "w"), ensure_ascii=False, indent=1)

for k in sorted(videos, key=lambda n: int(re.search(r"\d+", n).group())):
    print("%-10s %2d話" % (k, len(videos[k])), file=sys.stderr)
print("SP %d 本 / 合計 %d 本"
      % (len(sp), sum(len(v) for v in videos.values()) + len(sp)), file=sys.stderr)
