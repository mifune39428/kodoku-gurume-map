#!/usr/bin/env python3
"""Season11 は 8888 側が第3話までしか無いので、孤独のグルメ情報WEB から全12話ぶんを取る。"""
import html
import json
import os
import re
import subprocess

BASE = [
    ("2026/04/04", 1), ("2026/04/11", 2), ("2026/04/18", 3), ("2026/04/25", 4),
    ("2026/05/02", 5), ("2026/05/10", 6), ("2026/05/16", 7), ("2026/05/23", 8),
    ("2026/05/30", 9), ("2026/06/06", 10), ("2026/06/13", 11), ("2026/06/19", 12),
]
os.makedirs("s11", exist_ok=True)

FIELD = r"(?:住所|TEL|電話|交通手段|営業時間|定休日|席数|予算)"


def text_of(path):
    h = open(path, encoding="utf-8").read()
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"</(p|li|h[1-6]|tr|div|figcaption)>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    lines = [re.sub(r"[ \t　]+", " ", l).strip() for l in t.split("\n")]
    return [l for l in lines if l]


shops = []
for date, ep in BASE:
    path = f"s11/ep{ep:02d}.html"
    if not os.path.exists(path):
        subprocess.run(["curl", "-sL", "-A", "Mozilla/5.0",
                        f"https://kodojo.main.jp/{date}/season11_{ep}/", "-o", path], check=True)
    lines = text_of(path)
    # 「あわせて読みたい」以降は他記事の紹介なので切る
    for i, l in enumerate(lines):
        if "あわせて読みたい" in l or "聖地巡礼レポート" in l:
            lines = lines[:i]
            break

    for i, l in enumerate(lines):
        if not l.startswith("住所"):
            continue
        rec = {"season": "Season 11", "year": 2026, "episode": ep}
        # 直前の『店名』行をさかのぼって探す
        for j in range(i - 1, max(-1, i - 6), -1):
            m = re.match(r"^『(.+?)』$", lines[j])
            if m:
                rec["name"] = re.sub(r"（.+?）|\(.+?\)$", "", m.group(1)).strip()
                break
        rec["address"] = l.split("：", 1)[-1].split(":", 1)[-1].strip()
        for k in range(i + 1, min(len(lines), i + 12)):
            nxt = lines[k]
            if re.match(r"^『", nxt):
                break
            m = re.match(rf"^({FIELD})[：:](.*)$", nxt)
            if not m:
                if nxt.startswith("https://tabelog.com"):
                    rec["tabelog"] = nxt.strip()
                continue
            key, val = m.group(1), m.group(2).strip()
            if key == "定休日":
                rec["holiday"] = val
            elif key == "営業時間":
                rec["hours"] = val
            elif key in ("TEL", "電話"):
                tel = re.match(r"[\d\-]+", val)
                if tel:
                    rec["tel"] = tel.group(0)
        if rec.get("name") and rec.get("address"):
            shops.append(rec)

json.dump(shops, open("s11_shops.json", "w"), ensure_ascii=False, indent=1)
print(f"{len(shops)} 件")
for s in shops:
    print(f"  {s['episode']:2d} {s['name'][:24]:24} {s['address'][:30]:30} 定休日={s.get('holiday','-')}")
