#!/usr/bin/env python3
"""詳細ページの店舗データに閉店フラグを突き合わせ、座標を検証して最終JSONを作る。"""
import json
import math
import re
import time
import urllib.parse
import urllib.request

detail = json.load(open("shops_detail.json"))
raw = json.load(open("shops_raw.json"))

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]+")


def norm(name: str) -> str:
    n = EMOJI.sub("", name)
    n = re.sub(r"[『』「」()（）\s・･,、。\.]|【[^】]*】", "", n)
    n = re.sub(r"(本店|支店|\d+号店|店)$", "", n)
    return n.lower()


def season_key(label: str) -> str:
    m = re.search(r"Season\s*(\d+)", label)
    if m:
        return f"S{int(m.group(1))}"
    if "それぞれ" in label:
        return "EACH"
    return label


# --- 一覧ページの閉店フラグを突き合わせる -----------------------------------
flags = {}
for r in raw:
    flags.setdefault(season_key(r["season"]), {})[norm(r["name"])] = r["status"]

matched = 0
for s in detail:
    table = flags.get(season_key(s["season"]), {})
    key = norm(s["name"])
    hit = table.get(key)
    if hit is None:  # 部分一致で救う
        for k, v in table.items():
            if len(k) >= 3 and (k in key or key in k):
                hit, key = v, k
                break
    if hit is None:
        continue
    matched += 1
    if hit in ("closed", "hiatus"):
        s["status"] = hit
    elif s.get("status") == "closed":
        s.pop("status")  # 一覧が営業中としているなら誤検出
print(f"一覧と突き合わせできた店舗: {matched}/{len(detail)}")


# --- 座標の検証 --------------------------------------------------------------
CACHE_PATH = "geocode_cache.json"
try:
    cache = json.load(open(CACHE_PATH))
except FileNotFoundError:
    cache = {}


def gsi_geocode(address: str):
    if address in cache:
        return cache[address]
    url = "https://msearch.gsi.go.jp/address-search/AddressSearch?q=" + urllib.parse.quote(address)
    try:
        with urllib.request.urlopen(url, timeout=20) as fh:
            data = json.load(fh)
        if data:
            lng, lat = data[0]["geometry"]["coordinates"]
            cache[address] = [lat, lng]
        else:
            cache[address] = None
    except Exception as exc:  # ネットワーク由来の失敗は None 扱い
        print(f"  geocode失敗 {address}: {exc}")
        cache[address] = None
    time.sleep(0.4)
    return cache[address]


def km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    return 6371 * math.acos(min(1, math.sin(math.radians(la1)) * math.sin(math.radians(la2))
                                + math.cos(math.radians(la1)) * math.cos(math.radians(la2))
                                * math.cos(math.radians(lo2 - lo1))))


fixed, nocoord = 0, []
for s in detail:
    addr = s.get("address")
    embed = (s["lat"], s["lng"]) if "lat" in s else None
    geo = gsi_geocode(addr) if addr else None
    if embed and geo and km(embed, geo) > 2:
        s["lat"], s["lng"] = geo          # 埋め込み地図のピンが明らかにずれている
        s["geo_source"] = "gsi"
        fixed += 1
    elif embed:
        s["geo_source"] = "embed"
    elif geo:
        s["lat"], s["lng"] = geo
        s["geo_source"] = "gsi"
    else:
        nocoord.append(s)

json.dump(cache, open(CACHE_PATH, "w"), ensure_ascii=False)
print(f"座標を住所側に置き換え: {fixed} 件")
print(f"座標なし: {len(nocoord)} 件")
for s in nocoord:
    print("  ", s["season"], s.get("episode"), s["name"], s.get("address"))

json.dump(detail, open("shops_checked.json", "w"), ensure_ascii=False, indent=1)
print(f"閉店: {sum(s.get('status') == 'closed' for s in detail)} / "
      f"臨時休業: {sum(s.get('status') == 'hiatus' for s in detail)}")
