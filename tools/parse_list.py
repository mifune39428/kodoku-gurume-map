#!/usr/bin/env python3
"""8888-info の孤独のグルメ ロケ地一覧ページを構造化データに変換する。"""
import html
import json
import re
from urllib.parse import unquote

RAW = open("list_all.html", encoding="utf-8").read()

# 本文だけ切り出す
start = RAW.find("Season1(2012年)")
body = RAW[start:]

# 見出しとテーブル行をドキュメント順に拾う
TOKEN = re.compile(
    r"<h([345])[^>]*>(.*?)</h\1>|<tr>(.*?)</tr>",
    re.S,
)


def text_of(frag: str) -> str:
    frag = re.sub(r"<br\s*/?>", "\n", frag)
    frag = re.sub(r"<[^>]+>", "", frag)
    return html.unescape(frag).replace("　", " ").strip()


def tabelog_of(frag: str) -> str | None:
    for href in re.findall(r'href="([^"]+)"', frag):
        href = html.unescape(href)
        m = re.search(r"vc_url=([^&]+)", href)
        if m:
            url = unquote(m.group(1))
            if "tabelog.com" in url:
                return url
        if "tabelog.com" in href:
            return href.split("?")[0]
    return None


records = []
season = None
pref = None

for m in TOKEN.finditer(body):
    if m.group(1):  # 見出し
        level, txt = m.group(1), text_of(m.group(2))
        if level in ("3", "4"):
            # 「Season1 全12店舗／閉店3店舗」→「Season1」
            head = txt.split("　")[0].split(" ")[0]
            if head.startswith("Season") or "スペシャル" in txt or "それぞれ" in txt:
                season = txt
                pref = None
            elif re.match(r"^\d{4}【", txt):  # 大晦日SPなどの年別見出し
                season = f"{season.split('|')[0]}|{txt}" if season else txt
                pref = None
        elif level == "5":
            pref = txt
        continue

    row = m.group(3)
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
    if len(cells) < 2:
        continue
    left, right = text_of(cells[0]), text_of(cells[1])
    ep = re.search(r"第(\d+)話", left)
    if not ep:
        continue
    access = re.sub(r"^第\d+話\n?", "", left).replace("\n", " ").strip()

    # 右セル: 店名 + 【閉店】等 + リンクテキスト
    lines = [l.strip() for l in right.split("\n") if l.strip()]
    lines = [l for l in lines if l not in ("➡", "食べログ", "ホットペッパーグルメ", "→")]
    joined = " ".join(lines)
    status = "open"
    for kw, val in (("閉店", "closed"), ("閉業", "closed"), ("臨時休業", "hiatus")):
        if f"【{kw}】" in joined or kw in joined:
            status = val
            break
    name = re.sub(r"【[^】]*】", "", joined)
    name = re.sub(r"➡|食べログ|ホットペッパーグルメ", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        continue

    records.append(
        {
            "season": season,
            "episode": int(ep.group(1)),
            "pref": pref,
            "name": name,
            "status": status,
            "access": access,
            "tabelog": tabelog_of(cells[1]),
        }
    )

json.dump(records, open("shops_raw.json", "w"), ensure_ascii=False, indent=1)
print(f"{len(records)} records")
seasons = {}
for r in records:
    seasons.setdefault(r["season"], 0)
    seasons[r["season"]] += 1
for s, n in seasons.items():
    print(f"  {n:3d}  {s}")
