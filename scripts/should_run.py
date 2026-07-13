#!/usr/bin/env python3
"""
Zamanlama bekçisi: günde en fazla 3 video, belirli saat dilimlerinde.
Saatler (TR = UTC+3): 10:00, 17:00, 18:30, 21:00  ->  UTC: 07:00, 14:00, 15:30, 18:00
Her gün 4 slottan 1'i rotasyonla ATLANIR -> kalan 3 slot çalışır = günde 3.
Çıkış: 0 = ÇALIŞ, 1 = ATLA.
"""
import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLOTS_UTC = [(7, 0), (14, 0), (15, 30), (18, 0)]   # TR 10:00 / 17:00 / 18:30 / 21:00
DAILY_MAX = 3
WINDOW_MIN = 75   # cron gecikmesi toleransı

prog = ROOT / os.environ.get("PROGRESS_FILE", "state/motorsport_progress.json")
now = datetime.datetime.utcnow()
now_min = now.hour * 60 + now.minute
today = now.strftime("%Y-%m-%d")

# şu anki slot (en yakın, tolerans içinde)
cur = None
for i, (h, m) in enumerate(SLOTS_UTC):
    if abs(now_min - (h * 60 + m)) <= WINDOW_MIN:
        cur = i
        break

try:
    made = json.loads(prog.read_text(encoding="utf-8")).get("made", [])
except Exception:
    made = []
today_count = sum(1 for x in made if x.get("date") == today)

skip_slot = now.timetuple().tm_yday % len(SLOTS_UTC)   # bugün atlanacak slot (rotasyon)

reasons = []
if cur is None:
    reasons.append("planlı slot dışı")
if today_count >= DAILY_MAX:
    reasons.append(f"günlük limit dolu ({today_count}/{DAILY_MAX})")
if cur is not None and cur == skip_slot:
    reasons.append("bugünkü rotasyon-atlama slotu")

if reasons:
    print("ATLA:", "; ".join(reasons))
    sys.exit(1)
print(f"ÇALIŞ: slot {cur} (UTC {SLOTS_UTC[cur]}), bugün {today_count}/{DAILY_MAX}")
sys.exit(0)
