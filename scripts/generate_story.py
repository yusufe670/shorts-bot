#!/usr/bin/env python3
"""
AI-resimli HİKAYE Shorts üretici — tamamen ücretsiz.

Akış:
  hikaye bankasından sıradaki hikayeyi al
  -> her sahneyi Edge-TTS ile seslendir (kelime kelime zamanlama)
  -> her sahne için Pollinations.ai ile ÜCRETSİZ AI resim üret (key yok)
  -> resme yavaş zoom (Ken Burns) hareketi ver
  -> kelime kelime altyazı yak
  -> 9:16 (1080x1920), <=58 sn birleştir
  -> output/short.mp4  +  output/meta.json

TTS, altyazı ve montaj yardımcıları generate_video.py'den yeniden kullanılır.
"""
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_video as gv  # noqa: E402  (run, synth_all, chunk_words, render_caption_png, sabitler)
import seo  # noqa: E402  (SEO başlık/açıklama/etiket motoru)

ROOT = gv.ROOT
CONFIG = gv.CONFIG
BANK = ROOT / "content" / "stories.json"
STATE = ROOT / "state" / "story_progress.json"
OUT = gv.OUT
WORK = gv.WORK
W, H, FPS, MAX_SECONDS, CAP_Y = gv.W, gv.H, gv.FPS, gv.MAX_SECONDS, gv.CAP_Y

POLL_URL = "https://image.pollinations.ai/prompt/"


def gen_image(prompt, dest, seed):
    """Pollinations.ai ile ücretsiz AI resim üret. Başarısızsa gradyan yedeği."""
    full = (f"{prompt}. vertical 9:16 cinematic composition, no text, no words, "
            f"no watermark, no letters")
    url = (POLL_URL + urllib.parse.quote(full)
           + f"?width=1080&height=1920&nologo=true&model=flux&seed={seed}")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=120).read()
            if len(data) > 5000:
                dest.write_bytes(data)
                Image.open(dest).verify()   # gerçekten resim mi?
                return True
        except Exception as e:
            print(f"    resim denemesi {attempt+1} başarısız: {str(e)[:120]}")
            time.sleep(3)
    # yedek: koyu gradyan
    idx = seed % len(gv.GRADIENTS)
    c0, c1 = gv.GRADIENTS[idx]
    img = Image.new("RGB", (1080, 1920))
    top = tuple(int(c0[2:][i:i+2], 16) for i in (0, 2, 4))
    bot = tuple(int(c1[2:][i:i+2], 16) for i in (0, 2, 4))
    px = img.load()
    for y in range(1920):
        t = y / 1919
        col = tuple(int(top[k] + (bot[k] - top[k]) * t) for k in range(3))
        for x in range(1080):
            px[x, y] = col
    img.save(dest)
    return False


def ken_burns(image, duration, out_mp4, zoom_in=True):
    """Durağan resmi yavaş zoom'lu 1080x1920 klibe çevir."""
    frames = max(2, int(duration * FPS))
    if zoom_in:
        zexpr = "min(zoom+0.0009,1.20)"
    else:
        zexpr = "if(eq(on,0),1.20,max(zoom-0.0009,1.0))"
    vf = (f"scale=1620:2880:force_original_aspect_ratio=increase,crop=1620:2880,"
          f"zoompan=z='{zexpr}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"s={W}x{H}:fps={FPS},setsar=1")
    gv.run(["ffmpeg", "-y", "-loop", "1", "-i", str(image), "-t", f"{duration:.3f}",
            "-r", str(FPS), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", str(out_mp4)],
           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_mp4


def build_meta(story, cfg):
    title = story["title"].strip()
    if "#short" not in title.lower():
        title = (title[:88] + " #shorts")[:100]
    tags = list(dict.fromkeys(story.get("tags", []) + cfg.get("tags", []) + ["shorts", "story"]))
    total, trimmed = 0, []
    for t in tags:
        total += len(t) + 1
        if total > 480:
            break
        trimmed.append(t)
    desc_tmpl = cfg.get("description_template", "{title}\n\n{series}#shorts")
    description = desc_tmpl.format(title=story["title"].strip(), series="")
    return {"title": title, "description": description, "tags": trimmed,
            "categoryId": str(cfg.get("categoryId", "24")),
            "privacyStatus": cfg.get("privacyStatus", "public"),
            "madeForKids": bool(cfg.get("madeForKids", False)),
            "defaultLanguage": cfg.get("defaultLanguage", "en")}


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    if not bank:
        print("Hikaye bankası boş!"); return 1
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        state = {"next_index": 0, "made": []}
    idx = int(state.get("next_index", 0)) % len(bank)
    story = bank[idx]
    voice = cfg.get("voice", "en-US-AriaNeural")
    style = story.get("style", "cinematic storybook illustration, dramatic lighting")
    character = story.get("character", "")
    print(f"[{idx}] {story['title']}  ({len(story['scenes'])} sahne)")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    # 1) TTS + zaman çizelgesi; 58 sn'yi aşan sahneleri at
    scenes = story["scenes"]
    synth = gv.synth_all([{"text": s["text"]} for s in scenes], voice)
    kept, total = [], 0.0
    for (mp3, dur, gwords), sc in zip(synth, scenes):
        if total + dur > MAX_SECONDS and kept:
            break
        kept.append((mp3, dur, gwords, sc)); total += dur
    print(f"  {len(kept)} sahne, toplam {total:.1f} sn")

    # 2) ses birleştir
    voice_all = WORK / "voice.mp3"
    alist = WORK / "alist.txt"
    alist.write_text("".join(f"file '{m.as_posix()}'\n" for m, *_ in kept), encoding="utf-8")
    gv.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(alist),
            "-c", "copy", str(voice_all)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 3) her sahne için AI resim + Ken Burns segmenti
    base_seed = (abs(hash(story["id"])) % 90000) + 1000
    segs = []
    for i, (mp3, dur, gwords, sc) in enumerate(kept):
        scene_img = sc["image"].replace("the character", character) if character else sc["image"]
        prompt = f"{scene_img}. Art style: {style}."
        img = WORK / f"img_{i:02d}.jpg"
        ok = gen_image(prompt, img, base_seed + i)
        seg = ken_burns(img, dur, WORK / f"seg_{i:02d}.mp4", zoom_in=(i % 2 == 0))
        segs.append(seg)
        print(f"  sahne {i+1}/{len(kept)}: {'AI resim' if ok else 'gradyan yedek'}")
    vlist = WORK / "vlist.txt"
    vlist.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    bg = WORK / "bg.mp4"
    gv.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(vlist),
            "-c", "copy", str(bg)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4) altyazı PNG'leri
    all_words = [w for (_, _, gw, _) in kept for w in gw]
    caps = gv.chunk_words(all_words)
    cap_imgs = []
    for j, (cs, ce, text) in enumerate(caps):
        p = WORK / f"cap_{j:03d}.png"
        w, h = gv.render_caption_png(text, p)
        cap_imgs.append((p, w, h, cs, ce))

    # 5) montaj: bg + altyazı overlay + ses
    inputs = ["-i", str(bg)]
    for (p, *_rest) in cap_imgs:
        inputs += ["-i", str(p)]
    inputs += ["-i", str(voice_all)]
    fc, last = [], "0:v"
    for k, (p, w, h, cs, ce) in enumerate(cap_imgs):
        x = int((W - w) / 2)
        y = int(CAP_Y - h / 2)
        out = f"v{k}"
        fc.append(f"[{last}][{k+1}:v]overlay={x}:{y}:enable='between(t,{cs:.3f},{ce:.3f})'[{out}]")
        last = out
    filter_complex = ";".join(fc) if fc else "[0:v]null[v0]"
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
    r = gv.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not final.exists():
        print("MONTAJ HATASI:\n", (r.stderr or "")[-1500:]); return 1

    meta = seo.build_seo_meta(story, cfg)
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BİTTİ -> {final}  ({gv.ffprobe_duration(final):.1f} sn)")
    print("Başlık:", meta["title"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
