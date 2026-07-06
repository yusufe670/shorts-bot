#!/usr/bin/env python3
"""
Yüklenen videoların performansını çeker ve kazananı raporlar.

- state/story_progress.json içindeki "made" listesindeki video_id'leri okur
- YouTube Data API ile izlenme/beğeni/yorum sayılarını alır
- En çok izlenenleri ve seri bazında ortalamaları sıralar
- analytics_report.md dosyasına yazar

Kimlik: YT_CLIENT_ID/SECRET/REFRESH (yükleme ile aynı) ya da YT_API_KEY.
"""
import json
import os
import sys
from pathlib import Path

from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / os.environ.get("PROGRESS_FILE", "state/story_progress.json")
REPORT = ROOT / "analytics_report.md"

TOKEN_URI = "https://oauth2.googleapis.com/token"
# Token yalnızca upload scope'uyla alındı; public istatistik okumak bununla da çalışır.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_service():
    # Public izlenme okumak için API key gerekir (upload OAuth token'ı okuyamaz).
    api_key = os.environ.get("YT_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "Analitik için YT_API_KEY gerekli.\n"
            "Google Cloud > APIs & Services > Credentials > Create Credentials > API key ile oluştur,\n"
            "sonra GitHub'da repo Settings > Secrets > Actions içine YT_API_KEY olarak ekle."
        )
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def fetch_stats(service, ids):
    stats = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        resp = service.videos().list(part="statistics,snippet", id=",".join(chunk)).execute()
        for it in resp.get("items", []):
            s = it.get("statistics", {})
            stats[it["id"]] = {
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
                "title": it.get("snippet", {}).get("title", ""),
            }
    return stats


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    made = state.get("made", [])
    if not made:
        print("Henüz yüklenen video yok."); return 0
    ids = [m["video_id"] for m in made if m.get("video_id")]
    id_series = {m["video_id"]: (m.get("series") or "—") for m in made if m.get("video_id")}

    service = get_service()
    stats = fetch_stats(service, ids)
    rows = []
    for vid, st in stats.items():
        st["series"] = id_series.get(vid, "—")
        st["id"] = vid
        rows.append(st)
    rows.sort(key=lambda r: r["views"], reverse=True)

    # seri bazında ortalama
    by_series = {}
    for r in rows:
        by_series.setdefault(r["series"], []).append(r["views"])
    series_avg = {k: sum(v) / len(v) for k, v in by_series.items()}

    total_v = sum(r["views"] for r in rows)
    lines = [
        "# 📊 Kanal Performans Raporu", "",
        f"**Video sayısı:** {len(rows)}  |  **Toplam izlenme:** {total_v:,}  |  "
        f"**Video başı ort.:** {total_v // max(1, len(rows)):,}", "",
        "## 🏆 En çok izlenen 10 video", "",
        "| # | İzlenme | Beğeni | Yorum | Seri | Başlık |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows[:10], 1):
        lines.append(f"| {i} | {r['views']:,} | {r['likes']:,} | {r['comments']:,} | "
                     f"{r['series']} | {r['title'][:50]} |")
    lines += ["", "## 📈 Seri bazında ortalama izlenme (kazananı çoğalt)", ""]
    for k, v in sorted(series_avg.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- **{k}**: ort. {v:,.0f} izlenme ({len(by_series[k])} video)")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nRapor yazıldı: {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
