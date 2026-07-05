#!/usr/bin/env python3
"""
Uzun bir videoyu <= 58 saniyelik parçalara böler.
Bir kez, kendi bilgisayarında çalıştırılır (ffmpeg gerekir).

Her parça AYRI AYRI ve tam süreyle kesilir; böylece hiçbir parça
59 saniyeyi AŞMAZ (Shorts sınırı garanti).

Kullanım:
    python scripts/split.py source/video.mp4

Sonuç: parts/part_000.mp4, parts/part_001.mp4, ...
Bu parçaları commit edip GitHub'a push edersin; gerisini Actions halleder.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTS_DIR = ROOT / "parts"
CONFIG = ROOT / "config.json"


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def vertical_filter():
    # Videoyu 1080x1920 dikey tuvale oturt; arka planı bulanık aynı kareyle doldur
    return (
        "split[a][b];"
        "[a]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,gblur=sigma=20[bg];"
        "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python scripts/split.py <video-dosyası>")
        sys.exit(1)

    source = Path(sys.argv[1])
    if not source.exists():
        print(f"Bulunamadı: {source}")
        sys.exit(1)

    cfg = load_config()
    seg = int(cfg.get("segment_seconds", 58))
    seg = min(seg, 59)  # 59 sn üstüne asla çıkma
    vertical = bool(cfg.get("reencode_vertical", False))

    PARTS_DIR.mkdir(exist_ok=True)
    for old in PARTS_DIR.glob("part_*.mp4"):
        old.unlink()

    dur = ffprobe_duration(source)
    count = math.ceil(dur / seg)
    print(f"Kaynak süresi: {dur:.0f} sn -> {count} parça (parça başına <= {seg} sn)")

    for i in range(count):
        start = i * seg
        out = PARTS_DIR / f"part_{i:03d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),          # -i'den ÖNCE: hızlı ve re-encode ile tam isabetli
            "-i", str(source),
            "-t", str(seg),             # tam süre -> asla 59 sn'yi aşmaz
        ]
        if vertical:
            cmd += ["-vf", vertical_filter()]
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(out),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  [{i + 1}/{count}] {out.name}")

    parts = sorted(PARTS_DIR.glob("part_*.mp4"))
    print(f"\nBitti. {len(parts)} parça oluşturuldu -> {PARTS_DIR}")
    print("Sonraki adım: state/progress.json içindeki next_index'i 0 yap,"
          " parts/ ile birlikte commit + push et.")


if __name__ == "__main__":
    main()
