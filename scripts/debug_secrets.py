#!/usr/bin/env python3
"""Teşhis: GitHub secret'larının uzunluk/format kontrolü. Gizli değer yazmaz."""
import os

EXPECT = {
    "YT_CLIENT_ID": (72, lambda v: v.endswith(".apps.googleusercontent.com")),
    "YT_CLIENT_SECRET": (35, lambda v: v.startswith("GOCSPX-")),
    "YT_REFRESH_TOKEN": (103, lambda v: v.startswith("1//")),
}

ok = True
for k, (exp_len, fmt) in EXPECT.items():
    v = os.environ.get(k, "")
    has_ws = v != v.strip()
    fmt_ok = fmt(v) if v else False
    len_ok = len(v) == exp_len
    if not (len_ok and fmt_ok and not has_ws):
        ok = False
    print(
        f"{k}: uzunluk={len(v)} (beklenen {exp_len}, {'OK' if len_ok else 'YANLIS'}) | "
        f"format={'OK' if fmt_ok else 'YANLIS'} | "
        f"bas/son bosluk={'VAR (SORUN)' if has_ws else 'yok'}"
    )

print("\nSONUC:", "Tum secretlar dogru gorunuyor ✓" if ok else "En az bir secret YANLIS ✗")
