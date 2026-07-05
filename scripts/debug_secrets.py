#!/usr/bin/env python3
"""Teşhis: GitHub secret'larının uzunluk/format/hash kontrolü. Gizli değer yazmaz."""
import hashlib
import os

# Yerelde (çalışan) doğru değerlerin sha256[:16] parmak izleri
EXPECT = {
    "YT_CLIENT_ID": (72, lambda v: v.endswith(".apps.googleusercontent.com"), "7423d13469078c50"),
    "YT_CLIENT_SECRET": (35, lambda v: v.startswith("GOCSPX-"), "f3a63becc2e95e5e"),
    "YT_REFRESH_TOKEN": (103, lambda v: v.startswith("1//"), "1d044086c5552a32"),
}

ok = True
for k, (exp_len, fmt, exp_hash) in EXPECT.items():
    v = os.environ.get(k, "")
    has_ws = v != v.strip()
    fmt_ok = fmt(v) if v else False
    len_ok = len(v) == exp_len
    got_hash = hashlib.sha256(v.encode()).hexdigest()[:16] if v else "(bos)"
    hash_ok = got_hash == exp_hash
    if not (len_ok and fmt_ok and not has_ws and hash_ok):
        ok = False
    print(
        f"{k}: uzunluk={len(v)} ({'OK' if len_ok else 'YANLIS'}) | "
        f"format={'OK' if fmt_ok else 'YANLIS'} | "
        f"bosluk={'VAR' if has_ws else 'yok'} | "
        f"hash={'ESLESTI ✓' if hash_ok else 'FARKLI ✗ (secret bozuk!)'}"
    )

print("\nSONUC:", "Tum secretlar yerel ile AYNI ✓" if ok else "En az bir secret FARKLI ✗ — o secret'i duzelt")
