#!/usr/bin/env python3
"""各シーズンの詳細ページから 店名/話数/住所/定休日/緯度経度/注文メニュー を抜き出す。"""
import glob
import html
import json
import os
import re
from urllib.parse import unquote

SEASON_LABEL = {
    "s01": ("Season 1", 2012), "s02": ("Season 2", 2012), "s03": ("Season 3", 2013),
    "s04": ("Season 4", 2014), "s05": ("Season 5", 2015), "s06": ("Season 6", 2017),
    "s07": ("Season 7", 2018), "s08": ("Season 8", 2019), "s09": ("Season 9", 2021),
    "s10": ("Season 10", 2022), "s11": ("Season 11", 2026),
    "sEach": ("それぞれの孤独のグルメ", 2024),
    "sp2017": ("大晦日SP 2017 瀬戸内出張編", 2017),
    "sp2018": ("大晦日SP 2018 京都・名古屋出張編", 2018),
    "sp2019": ("大晦日SP 2019 成田・福岡・釜山出張編", 2019),
    "sp2020": ("大晦日SP 2020 東京・神奈川・埼玉編", 2020),
    "sp2021": ("大晦日SP 2021 京都・兵庫・三重・静岡・東京編", 2021),
    "sp2022": ("大晦日SP 2022 北海道にお届け物編", 2022),
    "sp2023": ("大晦日SP 2023 沖縄・台湾への逃避行編", 2023),
    "sp2024": ("大晦日SP 2024 映画のフィルムを届ける旅", 2024),
    "sp2025": ("大晦日SP 2025 佐渡島～山形県編", 2025),
    "sm2014": ("真夏SP 2014 博多出張編", 2014),
    "sm2016": ("真夏SP 2016 東北・宮城出張編", 2016),
    "sn2016": ("お正月SP 2016 北海道・旭川出張編", 2016),
    "sn2017": ("お正月SP 2017 東京・神奈川で飯テロ編", 2017),
}
ORDER = list(SEASON_LABEL)


def plain(frag: str) -> str:
    frag = re.sub(r"<br\s*/?>", "\n", frag)
    frag = re.sub(r"<[^>]+>", "", frag)
    return html.unescape(frag).replace("　", " ").strip()


def body_of(raw: str) -> str:
    m = re.search(r'<div class="entry-content[^"]*">(.*?)(?:<div class="entry-footer|<footer)', raw, re.S)
    return m.group(1) if m else raw


def latlng(frag: str):
    m = re.search(r"!2d(-?\d+\.\d+)!3d(-?\d+\.\d+)", frag)
    if m:
        return float(m.group(2)), float(m.group(1))
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", frag)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def tabelog(frag: str):
    for href in re.findall(r'href="([^"]+)"', frag):
        href = html.unescape(href)
        m = re.search(r"vc_url=([^&]+)", href)
        if m and "tabelog.com" in unquote(m.group(1)):
            return unquote(m.group(1))
        if "tabelog.com" in href:
            return href.split("?")[0]
    return None


EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿️⬀-⯿]+"
)


def strip_name(title: str) -> str:
    name = EMOJI_RE.sub("", title)
    name = re.sub(r"【[^】]*】|[（(](?:閉店|閉業)[）)]", "", name)
    name = name.replace("『", " ").replace("』", " ").replace("「", " ").replace("」", " ")
    return re.sub(r"\s+", " ", name).strip()


# 見出しが店名ではなく回のあらすじだった場合を弾く
NOT_A_SHOP = re.compile(
    r"(?:都|道|府|県|区|市)[^\s]{0,10}(?:で|の)[^\s]*$|出張編|逃避行|お届け物|旅$|編$"
)


ADDR_RE = re.compile(r"(〒?\s*\d{3}-?\d{4})?\s*((?:北海道|東京都|(?:京都|大阪)府|.{2,3}県)[^\n]{3,60})")
PHONE_RE = re.compile(r"\d{2,4}-\d{2,4}-\d{3,4}")


HOLIDAY_KEY = r"(?:定休日|店休日|休業日)"
SECTION = r"(?:注文メニュー|注文グルメ|購入グルメ|住所|所在地|アクセス|MAP|Googleマップ|予約|営業時間)"


def parse_block(frag: str) -> dict:
    # 見出しに絵文字が付くページがあるので先に落としておく
    txt = EMOJI_RE.sub("", plain(frag))
    out = {}

    # 定休日
    m = re.search(HOLIDAY_KEY + r"[…:：]?\s*([^\n]*)", txt)
    if m and m.group(1).strip():
        out["holiday"] = m.group(1).strip().lstrip(".…").strip()
    elif "不定休" in txt:
        out["holiday"] = "不定休"

    # 営業時間（定休日行を除く）
    m = re.search(r"営業時間\n(.*?)(?=\n" + SECTION + r"|\Z)", txt, re.S)
    if m:
        hours = [l.strip() for l in m.group(1).split("\n")
                 if l.strip() and not re.match(HOLIDAY_KEY, l.strip()) and not l.startswith("※")]
        if hours:
            out["hours"] = " / ".join(hours[:4])

    # 住所
    m = re.search(r"(?:住所|所在地)\n(.*?)(?=\n" + SECTION + r"|\Z)", txt, re.S)
    chunk = m.group(1) if m else txt
    am = ADDR_RE.search(chunk) or ADDR_RE.search(txt)
    if am:
        out["address"] = re.sub(r"\s+", "", am.group(2))
        if am.group(1):
            out["zip"] = am.group(1).replace("〒", "").strip()
    if m:
        pm = PHONE_RE.search(m.group(1))
        if pm:
            out["tel"] = pm.group(0)

    # 注文メニュー
    m = re.search(r"(?:注文|購入)(?:メニュー|グルメ)\n(.*?)(?=\n" + SECTION + r"|\Z)", txt, re.S)
    if m:
        items = [re.sub(r"^[✅✔️・]+", "", l).strip() for l in m.group(1).split("\n")]
        items = [i for i in items if i and len(i) < 60][:8]
        if items:
            out["menu"] = items

    lat, lng = latlng(frag)
    if lat:
        out["lat"], out["lng"] = lat, lng
    tb = tabelog(frag)
    if tb:
        out["tabelog"] = tb
    # 「15時閉店」のような営業時間表記を拾わないよう、明確な表現だけを見る
    if re.search(r"(?:閉店|閉業|廃業)(?:され|し)(?:て|ま)|現在は(?:閉店|閉業)|【\s*(?:閉店|閉業)\s*】", txt):
        out["status"] = "closed"
    return out


shops = []
for path in sorted(glob.glob("pages/*.html"), key=lambda p: ORDER.index(os.path.basename(p)[:-5])):
    key = os.path.basename(path)[:-5]
    season, year = SEASON_LABEL[key]
    body = body_of(open(path, encoding="utf-8").read())

    # h3 = 話数見出し、h4 = 店名見出し
    marks = [(m.start(), m.group(1), plain(m.group(2)), m.end())
             for m in re.finditer(r"<h([34])[^>]*>(.*?)</h\1>", body, re.S)]
    episode, ep_title, auto_ep = None, None, 0
    for i, (pos, lvl, title, end) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        frag = body[end:stop]
        if lvl == "3":
            em = re.search(r"第(\d+)話", title)
            if em:
                episode = int(em.group(1))
                ep_title = title.split("：", 1)[-1].split(":", 1)[-1].strip()
                continue
            # SP ページは h3 が店名そのもの
            if not re.search(r"maps/embed|住所|所在地", frag):
                continue
            auto_ep += 1
            episode, ep_title = auto_ep, None
        elif not re.search(r"maps/embed|住所|所在地", frag):
            continue
        name = strip_name(title)
        if not name or len(name) > 40 or re.match(r"^(はじめに|最後に|まとめ|注文|予約|営業|住所|所在地|MAP|アクセス)", name):
            continue
        if re.search(r"駅(から|より).{0,10}(徒歩|車|バス)", name):  # アクセス見出し
            continue
        if NOT_A_SHOP.search(name):  # 回のあらすじ見出し
            continue
        rec = {"season": season, "year": year, "episode": episode,
               "ep_title": ep_title, "name": name}
        rec.update(parse_block(frag))
        shops.append(rec)

json.dump(shops, open("shops_detail.json", "w"), ensure_ascii=False, indent=1)
print(f"{len(shops)} shops")
miss_ll = [s for s in shops if "lat" not in s]
miss_ad = [s for s in shops if "address" not in s]
print(f"座標なし {len(miss_ll)} / 住所なし {len(miss_ad)} / 定休日あり {sum('holiday' in s for s in shops)}")
from collections import Counter
for k, v in Counter(s["season"] for s in shops).items():
    print(f"  {v:3d}  {k}")
