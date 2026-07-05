#!/usr/bin/env python3
"""
BİR KEZ çalıştırılır: YouTube hesabın için kalıcı bir 'refresh token' üretir.
Bu token'ı GitHub'da secret olarak saklarsın; Actions onunla senin adına yükler.

Ön koşul:
  1. Google Cloud Console'da bir proje aç, "YouTube Data API v3"ü etkinleştir.
  2. OAuth istemcisi (tür: Desktop app) oluştur, JSON'u indir -> client_secret.json
     olarak bu klasöre koy.
  3. OAuth consent screen'de kendi Google hesabını "Test user" olarak ekle.

Kullanım:
    python scripts/get_token.py
Tarayıcı açılır, hesabınla giriş yaparsın, ekrana YT_REFRESH_TOKEN yazılır.
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
CLIENT_SECRET = ROOT / "client_secret.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    if not CLIENT_SECRET.exists():
        raise SystemExit(
            "client_secret.json bulunamadı. Google Cloud'dan indirip bu klasöre koy."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        authorization_prompt_message=(
            "\nTarayıcı açılıyor. Açılmazsa şu adrese git:\n{url}\n"
        ),
        success_message="Bitti! Bu sekmeyi kapatabilirsin.",
    )

    data = json.loads(CLIENT_SECRET.read_text(encoding="utf-8"))
    info = data.get("installed") or data.get("web") or {}

    lines = [
        "YT_CLIENT_ID=" + info.get("client_id", ""),
        "YT_CLIENT_SECRET=" + info.get("client_secret", ""),
        "YT_REFRESH_TOKEN=" + (creds.refresh_token or ""),
    ]
    (ROOT / "github_secrets.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n================  GitHub Secrets olarak ekle  ================\n")
    print("\n".join(lines))
    print("\n=============================================================")
    print("Bu 3 değer github_secrets.txt dosyasına da yazıldı.")


if __name__ == "__main__":
    main()
