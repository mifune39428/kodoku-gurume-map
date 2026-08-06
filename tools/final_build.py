#!/usr/bin/env python3
"""全ソースを統合して、マップが読み込む shops.json を作る。"""
import json
import math
import re
import time
import urllib.parse
import urllib.request

detail = json.load(open("shops_checked.json"))
s11 = json.load(open("s11_shops.json"))
status_list = json.load(open("status_list.json"))

S11_TITLES = {
    1: "藤沢市大庭のさばみりんと豚汁", 2: "港区西麻布のタンドリーチキンとマトン・マサラ",
    3: "文京区千石のラムスパイシー炒めと麻婆豆腐", 4: "厚木市のバーニャカウダと脾臓のパニーニ",
    5: "横浜市上飯田町のブンティットヌングとチャージョー", 6: "目黒区池尻大橋の豚のうす切鉄板焼とハンバーグステーキ",
    7: "北区東十条のカジキのムニエル", 8: "蓮田市の台湾ラーメンと水餃子",
    9: "取手市のレバステーキ定食とホルモン焼きと餃子", 10: "市原市高滝のアジフライとハガツオフライの定食",
    11: "横芝光町のまぐろガーリック焼定食と2色づけ丼", 12: "葛飾区高砂のかつ煮定食と稲庭うどん",
}

# 出典に地図・住所が載っておらず取りこぼした店を手当てする
MANUAL = [
    {"season": "Season 1", "year": 2012, "episode": 2, "ep_title": "豊島区駒込の煮魚定食",
     "name": "家庭料理 和食亭", "address": "東京都北区中里1-8-7", "holiday": "日曜日",
     "hours": "11時30分～13時30分 / 17時00分～22時00分",
     "menu": ["煮魚定食", "ひじきの煮物", "ほうれん草の胡麻和え"],
     "tabelog": "https://tabelog.com/tokyo/A1323/A132301/13126067/"},
]

# Season 11 は情報WEB 側のデータで置き換える
shops = [s for s in detail if s["season"] != "Season 11"] + MANUAL
for s in s11:
    s["ep_title"] = S11_TITLES.get(s["episode"])
shops += s11

# --- Season11 のジオコーディング ---------------------------------------------
cache = json.load(open("geocode_cache.json"))


def gsi(address):
    if address in cache:
        return cache[address]
    url = "https://msearch.gsi.go.jp/address-search/AddressSearch?q=" + urllib.parse.quote(address)
    with urllib.request.urlopen(url, timeout=20) as fh:
        data = json.load(fh)
    cache[address] = [data[0]["geometry"]["coordinates"][1],
                      data[0]["geometry"]["coordinates"][0]] if data else None
    time.sleep(0.4)
    return cache[address]


for s in shops:
    if "lat" in s:
        continue
    got = gsi(s["address"])
    if got:
        s["lat"], s["lng"] = got
        s["geo_source"] = "gsi"
json.dump(cache, open("geocode_cache.json", "w"), ensure_ascii=False)

# --- 営業状況をマージ ---------------------------------------------------------
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]+")


def norm(name):
    n = EMOJI.sub("", name)
    n = re.sub(r"[『』「」()（）\s・･,、。\.\-‐―ー_]|【[^】]*】", "", n)
    n = re.sub(r"(本店|支店|\d+号店|店)$", "", n)
    return n.lower()


def season_no(label):
    m = re.search(r"Season\s*(\d+)", label)
    return int(m.group(1)) if m else None


reg = {}
for r in status_list:
    reg.setdefault(norm(r["name"]), []).append(r)

merged = 0
for s in shops:
    key = norm(s["name"])
    mine = season_no(s["season"])
    hits = reg.get(key)
    if not hits:
        # 部分一致。短い名前は同じシーズンのものに限って許す
        cands = []
        for k, v in reg.items():
            if len(k) < 2 or not (k in key or key in k):
                continue
            same = [r for r in v if season_no(r["season"]) == mine] if mine else []
            if len(k) >= 3 or same:
                cands += same or v
        hits = cands or None
    if not hits:
        continue
    merged += 1
    hit = hits[0]
    for h in hits:  # 同名が複数あればシーズン→話数の一致を優先
        if season_no(h["season"]) == mine and h.get("episode") == s.get("episode"):
            hit = h
            break
        if h.get("episode") == s.get("episode"):
            hit = h
    s["status"] = hit["status"]
    if hit.get("note"):
        s["status_note"] = hit["note"]
print(f"営業状況を突き合わせ: {merged}/{len(shops)}")

# --- 整形 ---------------------------------------------------------------------
SP_RE = re.compile(r"SP|スペシャル|それぞれ")
NOT_SHOP = {"屋台で注文したメニュー"}
GARBAGE_HOLIDAY = re.compile(r"チェックし忘れ|不明|わからな")
out = []
for s in shops:
    if "lat" not in s:
        print("  座標なし:", s["season"], s["name"])
        continue
    s["name"] = re.sub(r"\s*(店舗情報|で移転オープン|として移転オープン)\s*$", "", s["name"]).strip()
    if s["name"] in NOT_SHOP:
        continue
    if s.get("address"):
        s["address"] = s["address"].lstrip("・･ ").strip()
    if s.get("holiday") and GARBAGE_HOLIDAY.search(s["holiday"]):
        s.pop("holiday")
    hrs = s.get("hours", "")
    if hrs in ("ー", "-", "―") or re.search(r"閉業|閉店|@|http", hrs) or len(hrs) > 80:
        s.pop("hours", None)
    rec = {
        "name": s["name"],
        "season": s["season"],
        "year": s["year"],
        "episode": s.get("episode"),
        "ep_title": s.get("ep_title"),
        "is_sp": bool(SP_RE.search(s["season"])),
        "status": s.get("status", "open"),
        "lat": round(s["lat"], 6),
        "lng": round(s["lng"], 6),
    }
    for k in ("address", "holiday", "hours", "tel", "menu", "tabelog", "status_note", "geo_source"):
        if s.get(k):
            rec[k] = s[k]
    out.append(rec)

out.sort(key=lambda r: (r["year"], r["season"], r["episode"] or 0))
json.dump(out, open("shops.json", "w"), ensure_ascii=False, indent=1)

from collections import Counter
print(f"\n合計 {len(out)} 店")
print("状況:", dict(Counter(r["status"] for r in out)))
print("定休日あり:", sum("holiday" in r for r in out))
for k, v in Counter(r["season"] for r in out).items():
    print(f"  {v:3d}  {k}")
