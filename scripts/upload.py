#!/usr/bin/env python3
"""
Sıradaki parçayı YouTube'a yükler ve ilerlemeyi kaydeder.
GitHub Actions her tetiklendiğinde SADECE 1 parça yükler.

Gerekli ortam değişkenleri (GitHub Secrets):
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metadata import build_metadata  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARTS_DIR = ROOT / "parts"
CONFIG = ROOT / "config.json"
PROGRESS = ROOT / "state" / "progress.json"

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_progress(data):
    PROGRESS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_service():
    cid = os.environ.get("YT_CLIENT_ID")
    csecret = os.environ.get("YT_CLIENT_SECRET")
    refresh = os.environ.get("YT_REFRESH_TOKEN")
    if not all([cid, csecret, refresh]):
        raise SystemExit(
            "Eksik secret: YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN"
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh,
        client_id=cid,
        client_secret=csecret,
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def main():
    cfg = load_json(CONFIG)
    progress = load_json(PROGRESS)
    index = int(progress.get("next_index", 0))

    part = PARTS_DIR / f"part_{index:03d}.mp4"
    if not part.exists():
        print(f"Yüklenecek parça kalmadı (index={index}). Tüm seri bitti ✅")
        return 0

    meta = build_metadata(index, cfg)
    print(f"Yükleniyor: {part.name}")
    print(f"Başlık: {meta['title']}")

    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": str(cfg.get("categoryId", "24")),
            "defaultLanguage": cfg.get("defaultLanguage", "tr"),
            "defaultAudioLanguage": cfg.get("defaultLanguage", "tr"),
        },
        "status": {
            "privacyStatus": cfg.get("privacyStatus", "public"),
            "selfDeclaredMadeForKids": bool(cfg.get("madeForKids", False)),
        },
    }

    service = get_service()
    media = MediaFileUpload(str(part), chunksize=-1, resumable=True, mimetype="video/mp4")

    try:
        request = service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  ... %{int(status.progress() * 100)}")
        video_id = response["id"]
        print(f"✅ Yüklendi: https://youtu.be/{video_id}")
    except HttpError as e:
        print(f"❌ YouTube API hatası: {e}")
        # Kotayı aştıysak ilerlemeyi ARTIRMA; bir sonraki çalışmada tekrar dener.
        if e.resp.status in (403, 400):
            return 1
        return 1

    progress["next_index"] = index + 1
    progress.setdefault("uploaded", []).append(
        {"index": index, "video_id": video_id, "title": meta["title"]}
    )
    save_progress(progress)
    print(f"İlerleme kaydedildi. Sıradaki index: {index + 1}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
