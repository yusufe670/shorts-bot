#!/usr/bin/env python3
"""
AI Shorts üretici — tamamen ücretsiz.

Akış:
  içerik bankasından sıradaki bilgiyi al
  -> Edge-TTS ile seslendir (kelime kelime zamanlama)
  -> her cümleye uygun Pexels dikey stok klip indir (yoksa gradyan arka plan)
  -> kelime kelime altyazı yak (Pillow PNG overlay, fontconfig'e ihtiyaç yok)
  -> 9:16 (1080x1920), <=58 sn birleştir
  -> output/short.mp4  +  output/meta.json

Çıktıyı upload_generated.py YouTube'a yükler.
"""
import asyncio
import json
import os
import random
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import edge_tts
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
BANK = ROOT / "content" / "facts.json"
STATE = ROOT / "state" / "content_progress.json"
FONT = ROOT / "assets" / "fonts" / "Anton-Regular.ttf"
OUT = ROOT / "output"
WORK = OUT / "work"

W, H, FPS = 1080, 1920, 30
MAX_SECONDS = 58.0
CAP_MAX_WORDS = 3          # altyazı öbeği başına kelime
CAP_Y = int(H * 0.60)      # altyazı dikey konumu (orta-alt)

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# gradyan yedeği için konuya göre renk çiftleri
GRADIENTS = [
    ("0x0f2027", "0x2c5364"), ("0x1a2a6c", "0xb21f1f"), ("0x000428", "0x004e92"),
    ("0x232526", "0x414345"), ("0x0f0c29", "0x302b63"), ("0x134e5e", "0x71b280"),
]


def run(cmd, **kw):
    return subprocess.run(cmd, creationflags=CREATE_NO_WINDOW, **kw)


def ffprobe_duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


# ----------------------------------------------------------------- TTS
async def _synth_line(text, voice, out_mp3):
    c = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    words, audio = [], bytearray()
    async for ch in c.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            words.append((ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]))
    out_mp3.write_bytes(bytes(audio))
    return words


def synth_all(lines, voice):
    """Her satırı seslendir; global (start,end,word) zaman çizelgesi kur."""
    results = []          # (mp3_path, duration, [(g_start,g_end,word)...])
    cursor = 0.0
    for i, ln in enumerate(lines):
        mp3 = WORK / f"voice_{i:02d}.mp3"
        words = asyncio.run(_synth_line(ln["text"], voice, mp3))
        dur = ffprobe_duration(mp3)
        gwords = [(cursor + o, cursor + o + d, w) for (o, d, w) in words]
        results.append((mp3, dur, gwords))
        cursor += dur
    return results


# ----------------------------------------------------------------- Pexels
def pexels_clip(keyword, min_seconds, dest):
    """Anahtar kelimeye uygun dikey stok video indir. Başarısızsa None."""
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return None
    try:
        url = ("https://api.pexels.com/videos/search?query="
               + urllib.request.quote(keyword)
               + "&orientation=portrait&per_page=8&size=medium")
        req = urllib.request.Request(url, headers={"Authorization": key})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode())
        vids = data.get("videos") or []
        random.shuffle(vids)
        for v in vids:
            files = [f for f in v.get("video_files", [])
                     if f.get("height", 0) >= f.get("width", 1)      # dikey
                     and f.get("file_type") == "video/mp4"]
            if not files:
                continue
            # 1920'ye en yakın yüksekliği seç
            files.sort(key=lambda f: abs(f.get("height", 0) - 1920))
            link = files[0]["link"]
            urllib.request.urlretrieve(link, dest)
            if dest.exists() and dest.stat().st_size > 10000:
                return dest
    except Exception as e:
        print(f"  Pexels '{keyword}' atlandı: {e}")
    return None


def make_segment(index, keyword, duration, out_mp4):
    """Bir satır için 1080x1920 arka plan segmenti üret (Pexels ya da gradyan)."""
    raw = pexels_clip(keyword, duration, WORK / f"raw_{index:02d}.mp4")
    dur = max(0.8, duration)
    if raw:
        # kırp + ölçekle(cover) + kırp + döngüyle süreyi doldur
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},setsar=1,fps={FPS}")
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(raw), "-t", f"{dur:.3f}",
             "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", str(out_mp4)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if out_mp4.exists() and out_mp4.stat().st_size > 0:
            return out_mp4
    # gradyan yedeği (yavaş kayan)
    c0, c1 = GRADIENTS[index % len(GRADIENTS)]
    src = (f"gradients=s={W}x{H}:c0={c0}:c1={c1}:x0=0:y0=0:x1={W}:y1={H}"
           f":duration={dur:.3f}:speed=0.008:rate={FPS}")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-t", f"{dur:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out_mp4)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_mp4


# ----------------------------------------------------------------- Altyazı
def chunk_words(words):
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        chars = sum(len(x[2]) for x in cur) + len(cur) - 1
        if len(cur) >= CAP_MAX_WORDS or chars >= 16:
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    out = []
    for c in chunks:
        text = " ".join(x[2] for x in c).upper()
        out.append((c[0][0], c[-1][1], text))
    return out


def render_caption_png(text, path):
    """Kalın beyaz + siyah kontur altyazıyı şeffaf PNG olarak çiz."""
    size = 96
    stroke = 10
    pad = 24
    while size > 40:
        font = ImageFont.truetype(str(FONT), size)
        bbox = font.getbbox(text, stroke_width=stroke)
        tw = bbox[2] - bbox[0]
        if tw <= W - 80:
            break
        size -= 6
    font = ImageFont.truetype(str(FONT), size)
    bbox = font.getbbox(text, stroke_width=stroke)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=(255, 255, 255, 255),
           stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    img.save(path)
    return img.size


# ----------------------------------------------------------------- Montaj
def build_meta(item, cfg):
    title = item["title"].strip()
    if "#short" not in title.lower():
        title = (title[:88] + " #shorts")[:100]
    tags = list(dict.fromkeys(item.get("tags", []) + cfg.get("tags", []) + ["shorts"]))
    total, trimmed = 0, []
    for t in tags:
        total += len(t) + 1
        if total > 480:
            break
        trimmed.append(t)
    desc_tmpl = cfg.get("description_template", "{title}\n\n#shorts")
    description = desc_tmpl.format(title=item["title"].strip(), series="")
    return {"title": title, "description": description, "tags": trimmed,
            "categoryId": str(cfg.get("categoryId", "27")),
            "privacyStatus": cfg.get("privacyStatus", "public"),
            "madeForKids": bool(cfg.get("madeForKids", False)),
            "defaultLanguage": cfg.get("defaultLanguage", "en")}


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    if not bank:
        print("İçerik bankası boş!"); return 1
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        state = {"next_index": 0, "made": []}
    idx = int(state.get("next_index", 0)) % len(bank)
    item = bank[idx]
    voice = cfg.get("voice", "en-US-AriaNeural")
    print(f"[{idx}] {item['title']}")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    # 1) TTS + zaman çizelgesi (58 sn'yi aşan satırları at)
    synth = synth_all(item["lines"], voice)
    kept, total = [], 0.0
    for (mp3, dur, gwords), ln in zip(synth, item["lines"]):
        if total + dur > MAX_SECONDS and kept:
            break
        kept.append((mp3, dur, gwords, ln["keyword"])); total += dur
    print(f"  {len(kept)} satır, toplam {total:.1f} sn")

    # 2) ses birleştir
    voice_all = WORK / "voice.mp3"
    concat_list = WORK / "alist.txt"
    concat_list.write_text("".join(f"file '{m.as_posix()}'\n" for m, *_ in kept), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(voice_all)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 3) her satır için arka plan segmenti + birleştir
    seg_list = WORK / "vlist.txt"
    segs = []
    for i, (mp3, dur, gwords, keyword) in enumerate(kept):
        seg = make_segment(i, keyword, dur, WORK / f"seg_{i:02d}.mp4")
        segs.append(seg)
        print(f"  arka plan {i+1}/{len(kept)}: {keyword}")
    seg_list.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    bg = WORK / "bg.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(seg_list),
         "-c", "copy", str(bg)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4) altyazı PNG'leri
    all_words = [w for (_, _, gw, _) in kept for w in gw]
    caps = chunk_words(all_words)
    cap_imgs = []
    for j, (cs, ce, text) in enumerate(caps):
        p = WORK / f"cap_{j:03d}.png"
        w, h = render_caption_png(text, p)
        cap_imgs.append((p, w, h, cs, ce))

    # 5) montaj: bg + altyazı overlay'leri + ses
    inputs = ["-i", str(bg)]
    for (p, w, h, cs, ce) in cap_imgs:
        inputs += ["-i", str(p)]
    inputs += ["-i", str(voice_all)]

    fc = []
    last = "0:v"
    for k, (p, w, h, cs, ce) in enumerate(cap_imgs):
        x = int((W - w) / 2)
        y = int(CAP_Y - h / 2)
        img_in = k + 1
        out = f"v{k}"
        fc.append(f"[{last}][{img_in}:v]overlay={x}:{y}:enable='between(t,{cs:.3f},{ce:.3f})'[{out}]")
        last = out
    filter_complex = ";".join(fc) if fc else "[0:v]null[vv]"
    vmap = f"[{last}]" if fc else "0:v"
    audio_in = len(cap_imgs) + 1

    OUT.mkdir(exist_ok=True)
    final = OUT / "short.mp4"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
           "-map", vmap, "-map", f"{audio_in}:a",
           "-t", f"{min(total, MAX_SECONDS):.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-r", str(FPS), str(final)]
    r = run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not final.exists():
        print("MONTAJ HATASI:\n", r.stderr[-1500:]); return 1

    meta = build_meta(item, cfg)
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BİTTİ -> {final}  ({ffprobe_duration(final):.1f} sn)")
    print("Başlık:", meta["title"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
