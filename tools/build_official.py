#!/usr/bin/env python3
"""公式（テレビ東京）の各話ページ URL を確定させる。

シーズンごとに URL の付け方が違うのでテンプレートを個別に持ち、
可能なものは「そのページに 第N話 と書いてあるか」を1本ずつ確認する。

Season 4/5/6 は本文が JavaScript で描画されるため静的には確認できないが、
一覧ページのリンクが 01〜12 の連番で並んでいることを確認済み（Season 6 は
一覧に「#01 2017.04.07」と放送日が明記されていて話数と一致する）。
Season 10/11 は全話が1ページに載っていて各話ページが存在しないので一覧を指す。
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

TEMPLATE = {                                  # 話数 → URL（{e} が話数）
    1: BASE + "/kodokunogurume1/story/chapter{e}.html",
    2: BASE + "/kodokunogurume2/story/story{e}.html",
    4: BASE + "/kodokunogurume4/story/story{e:02d}.html",
    5: BASE + "/kodokunogurume5/backnumber/backnumber{e:02d}.html",
    6: BASE + "/kodokunogurume6/backnumber/backnumber{e:02d}.html",
    7: BASE + "/kodokunogurume7/smp/backnumber/backnumber{e}.html",
    8: BASE + "/kodokunogurume8/backnumber/backnumber{e}.html",
    9: BASE + "/kodokunogurume9/story/{e:02d}.html",
}
VERIFIABLE = {1, 2, 7, 8, 9}                  # 本文が静的で確認が効くシーズン
INDEX = {
    1: BASE + "/kodokunogurume1/story/",
    2: BASE + "/kodokunogurume2/story/",
    3: BASE + "/kodokunogurume3/story/",
    4: BASE + "/kodokunogurume4/story/",
    5: BASE + "/kodokunogurume5/backnumber/",
    6: BASE + "/kodokunogurume6/backnumber/",
    7: BASE + "/kodokunogurume7/backnumber/",
    8: BASE + "/kodokunogurume8/backnumber/",
    9: BASE + "/kodokunogurume9/story/",
    10: BASE + "/kodokunogurume10/backnumber/",
    11: BASE + "/kodokunogurume11/story/",
}
SP_SITE = {
    "真夏SP 2014 博多出張編": BASE + "/kodokunogurume4/story/storysp.html",
    "お正月SP 2016 北海道・旭川出張編": BASE + "/kodokunogurume_hokkaido_sp/",
    "真夏SP 2016 東北・宮城出張編": BASE + "/kodokunogurume_miyagi_sp/",
    "お正月SP 2017 東京・神奈川で飯テロ編": BASE + "/kodokunogurume_shougatsu_sp/",
    "大晦日SP 2017 瀬戸内出張編": BASE + "/kodokunogurume_setouchi_sp/",
    "大晦日SP 2018 京都・名古屋出張編": BASE + "/kodokunogurume_omisoka2018/",
    "大晦日SP 2019 成田・福岡・釜山出張編": BASE + "/kodokunogurume_omisoka2019/",
    "大晦日SP 2020 東京・神奈川・埼玉編": BASE + "/kodokunogurume_omisoka2020/",
    "大晦日SP 2021 京都・兵庫・三重・静岡・東京編": BASE + "/kodokunogurume_omisoka2021/",
    "大晦日SP 2022 北海道にお届け物編": BASE + "/kodokunogurume_omisoka2022/",
    "大晦日SP 2023 沖縄・台湾への逃避行編": BASE + "/kodokunogurume_omisoka2023/",
    "大晦日SP 2024 映画のフィルムを届ける旅": BASE + "/kodokunogurume_omisoka2024/",
    "大晦日SP 2025 佐渡島～山形県編": BASE + "/kodokunogurume_omisoka2025/",
    "それぞれの孤独のグルメ": BASE + "/kodokunogurume_sorezore/",
}
# 一覧ページ自体が最終話のページになっているシーズン
INDEX_IS_EPISODE = {1: 12, 2: 12, 3: 12}


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


def alive(page):
    return bool(page) and "お探しのページは見つかりません" not in page


def declares(page, ep):
    """タイトルか画像の alt に「第{ep}話」と書いてあるページか。"""
    if not alive(page):
        return False
    spots = re.findall(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    spots += re.findall(r'alt="([^"]*)"', page)
    for s in spots[:40]:
        s = htmllib.unescape(re.sub(r"<[^>]+>", "", s)).translate(ZEN)
        if ep == 12 and "最終話" in s:
            return True
        m = re.search(r"第?\s*(\d+)\s*話", s)
        if m:
            return int(m.group(1)) == ep
    return False


episodes = {}
for season, tpl in sorted(TEMPLATE.items()):
    hit = {}
    for ep in range(1, 13):
        url = tpl.format(e=ep)
        page = fetch(url)
        if season in VERIFIABLE:
            ok = declares(page, ep)
        else:
            ok = alive(page)          # 本文が JS 描画なので存在確認だけ
        if ok:
            hit[ep] = url
    if season in INDEX_IS_EPISODE:
        hit.setdefault(INDEX_IS_EPISODE[season], INDEX[season])
    episodes["Season %d" % season] = hit
    mark = "確認済" if season in VERIFIABLE else "連番"
    print("Season %-2d  %2d話  %s" % (season, len(hit), mark), file=sys.stderr)

# Season 3 は放送日がファイル名なので、一覧ページのリンクを1本ずつ確かめる
hit3 = {}
for path in sorted(set(re.findall(r'href="([^"]*kodokunogurume3/story/\d{4}\.html)"',
                                  fetch(INDEX[3])))):
    url = path if path.startswith("http") else BASE + path
    page = fetch(url)
    for ep in range(1, 13):
        if declares(page, ep):
            hit3[ep] = url
            break
hit3.setdefault(INDEX_IS_EPISODE[3], INDEX[3])
episodes["Season 3"] = hit3
print("Season 3    %2d話  確認済" % len(hit3), file=sys.stderr)

sp = {k: v for k, v in SP_SITE.items() if alive(fetch(v))}
for k in SP_SITE:
    if k not in sp:
        print("  SP のページが見つからない:", k, file=sys.stderr)

out = {
    "episodes": {k: {str(e): u for e, u in sorted(v.items())} for k, v in episodes.items()},
    "index": {"Season %d" % s: u for s, u in INDEX.items()},
    "sp": sp,
}
json.dump(out, open("official_map.json", "w"), ensure_ascii=False, indent=1)
print("\n各話リンク %d 本 / SP %d 本" % (sum(len(v) for v in episodes.values()), len(sp)),
      file=sys.stderr)
