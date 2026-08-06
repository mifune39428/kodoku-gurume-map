#!/usr/bin/env python3
"""孤独のグルメ情報WEB の全店舗リストから、店ごとの営業状況を取り出す。"""
import html
import json
import re

h = open("alllist.html", encoding="utf-8").read()
t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
t = re.sub(r"<br\s*/?>", "\n", t)
t = re.sub(r"</(p|li|h[1-6]|tr|div)>", "\n", t)
t = html.unescape(re.sub(r"<[^>]+>", "", t))
lines = [re.sub(r"\s+", " ", l).strip() for l in t.split("\n")]
lines = [l for l in lines if l]

ZEN = str.maketrans("０１２３４５６７８９", "0123456789")
STATUS = {"営業中": "open", "閉店済": "closed", "移転済": "moved", "休業中": "hiatus"}

records, season = [], None
for line in lines:
    if line.startswith("▼"):
        if line.startswith("▼原作"):
            break  # ここから先は原作漫画のリスト
        season = line[1:].split("（")[0].strip()
        continue
    m = re.search(r"\[(営業中|閉店済|移転済|休業中)\]\s*(.+)$", line)
    if not m:
        continue
    status, rest = STATUS[m.group(1)], m.group(2)
    parts = [p.strip() for p in rest.split("｜")]
    name = parts[0]
    pref = parts[1] if len(parts) > 1 else None
    area = parts[2] if len(parts) > 2 else None
    ep = note = None
    if len(parts) > 3:
        tail = parts[3].translate(ZEN)
        em = re.search(r"(\d+)話", tail)
        if em:
            ep = int(em.group(1))
        if "／" in tail:
            note = tail.split("／", 1)[1].strip()
        elif re.search(r"SP|スペシャル", tail):
            note = tail.strip()
    records.append({"season": season, "status": status, "name": name,
                    "pref": pref, "area": area, "episode": ep, "note": note})

json.dump(records, open("status_list.json", "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(len(records), Counter(r["status"] for r in records))
print(Counter(r["season"] for r in records))
