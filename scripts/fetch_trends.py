#!/usr/bin/env python3
"""
Google Trends günlük trend akışını (ücretsiz, key yok) çeker, state/trends.json'a yazar.
Bunları videolara ETİKET olarak enjekte ETMEZ (alakasız trend = spam = zarar).
Amaç: trend'leri görünür kılmak + trend-temalı içerik üretmek istendiğinde kaynak olmak.

Kullanım: python scripts/fetch_trends.py [US GB TR ...]
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "state" / "trends.json"


def fetch(geo):
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    items = re.findall(r"<item>(.*?)</item>", data, re.S)
    out = []
    for it in items:
        m = re.search(r"<title>(.*?)</title>", it, re.S)
        if m:
            t = re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1)).strip()
            if t:
                out.append(t)
    return out[:20]


def main():
    geos = sys.argv[1:] or ["US", "GB"]
    result = {}
    for g in geos:
        try:
            result[g] = fetch(g)
            print(f"{g}: {len(result[g])} trend")
        except Exception as e:
            print(f"{g} alınamadı: {str(e)[:100]}")
            result[g] = []
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Trendler ->", OUT)
    # ilk birkaçını göster
    for g, ts in result.items():
        if ts:
            print(f"  {g}:", ", ".join(ts[:6]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
