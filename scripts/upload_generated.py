#!/usr/bin/env python3
"""
output/short.mp4 dosyasını output/meta.json ile YouTube'a yükler,
sonra state/content_progress.json içindeki next_index'i artırır.

GitHub Actions akışı:  generate_video.py -> upload_generated.py -> commit

Gerekli secret'lar: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
VIDEO = OUT / "short.mp4"
META = OUT / "meta.json"
# Hangi ilerleme/bank dosyası kullanılacağı ortam değişkeniyle ayarlanır
# (hikaye modu için PROGRESS_FILE=state/story_progress.json, BANK_FILE=content/stories.json)
STATE = ROOT / os.environ.get("PROGRESS_FILE", "state/content_progress.json")
BANK = ROOT / os.environ.get("BANK_FILE", "content/facts.json")

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_service():
    cid = os.environ.get("YT_CLIENT_ID")
    csecret = os.environ.get("YT_CLIENT_SECRET")
    refresh = os.environ.get("YT_REFRESH_TOKEN")
    if not all([cid, csecret, refresh]):
        raise SystemExit("Eksik secret: YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN")
    creds = Credentials(
        token=None, refresh_token=refresh, client_id=cid, client_secret=csecret,
        token_uri=TOKEN_URI, scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def main():
    if not VIDEO.exists() or not META.exists():
        print("Yüklenecek video/meta bulunamadı — önce generate_video.py çalışmalı.")
        return 1
    meta = json.loads(META.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    index = int(state.get("next_index", 0))

    print(f"Yükleniyor (index={index}): {meta['title']}")
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta.get("tags", []),
            "categoryId": str(meta.get("categoryId", "27")),
            "defaultLanguage": meta.get("defaultLanguage", "en"),
            "defaultAudioLanguage": meta.get("defaultLanguage", "en"),
        },
        "status": {
            # YT_PRIVACY ortam değişkeni test için geçici olarak private yapabilir
            "privacyStatus": os.environ.get("YT_PRIVACY") or meta.get("privacyStatus", "public"),
            "selfDeclaredMadeForKids": bool(meta.get("madeForKids", False)),
        },
    }
    service = get_service()
    media = MediaFileUpload(str(VIDEO), chunksize=-1, resumable=True, mimetype="video/mp4")
    try:
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  ... %{int(status.progress() * 100)}")
        video_id = response["id"]
        print(f"✅ Yüklendi: https://youtu.be/{video_id}")
    except HttpError as e:
        print(f"❌ YouTube API hatası: {e}")
        return 1

    try:
        bank_len = len(json.loads(BANK.read_text(encoding="utf-8")))
    except Exception:
        bank_len = index + 1
    state["next_index"] = (index + 1) % max(1, bank_len)
    state.setdefault("made", []).append(
        {"index": index, "video_id": video_id, "title": meta["title"],
         "series": meta.get("series", "")}
    )
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"İlerleme kaydedildi. Sıradaki index: {state['next_index']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
