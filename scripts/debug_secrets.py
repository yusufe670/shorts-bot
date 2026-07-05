#!/usr/bin/env python3
"""Teşhis: secret hash kontrolü + gerçek refresh denemesi. Gizli değer yazmaz."""
import hashlib
import os

EXPECT = {
    "YT_CLIENT_ID": (72, lambda v: v.endswith(".apps.googleusercontent.com"), "7423d13469078c50"),
    "YT_CLIENT_SECRET": (35, lambda v: v.startswith("GOCSPX-"), "f3a63becc2e95e5e"),
    "YT_REFRESH_TOKEN": (103, lambda v: v.startswith("1//"), "1d044086c5552a32"),
}

for k, (exp_len, fmt, exp_hash) in EXPECT.items():
    v = os.environ.get(k, "")
    got_hash = hashlib.sha256(v.encode()).hexdigest()[:16] if v else "(bos)"
    print(f"{k}: uzunluk={len(v)} | hash={'ESLESTI' if got_hash==exp_hash else 'FARKLI'}")

print("\n--- GERCEK REFRESH DENEMESI ---")
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google.auth

print("google-auth surumu:", getattr(google.auth, "__version__", "?"))

c = Credentials(
    token=None,
    refresh_token=os.environ.get("YT_REFRESH_TOKEN"),
    client_id=os.environ.get("YT_CLIENT_ID"),
    client_secret=os.environ.get("YT_CLIENT_SECRET"),
    token_uri="https://oauth2.googleapis.com/token",
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
)
try:
    c.refresh(Request())
    print("REFRESH SONUC: BASARILI ✓ (access token alindi) — sorun refresh'te DEGIL")
except Exception as e:
    print("REFRESH SONUC: BASARISIZ ✗")
    print("  Hata tipi:", type(e).__name__)
    print("  Mesaj:", str(e)[:300])
