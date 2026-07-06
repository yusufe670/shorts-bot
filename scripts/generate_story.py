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
import random
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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


def _image_ok(path):
    """Kalite denetimi: bozuk / neredeyse boş / aşırı karanlık-parlak görseli ele."""
    try:
        im = Image.open(path).convert("L").resize((64, 114))
    except Exception:
        return False
    px = list(im.getdata())
    n = len(px)
    mean = sum(px) / n
    std = (sum((p - mean) ** 2 for p in px) / n) ** 0.5
    return std >= 14 and 12 <= mean <= 243   # düz/karanlık/parlak değilse geç


def gen_image(prompt, dest, seed):
    """Pollinations.ai ile ücretsiz AI resim (kalite denetimli). Başarısızsa gradyan."""
    full = (f"{prompt}. vertical 9:16 cinematic composition. "
            f"absolutely no text, no letters, no words, no captions, "
            f"no watermark, no signature, no numbers on the image")
    for attempt in range(4):
        s = seed + attempt * 7919   # her denemede farklı seed
        url = (POLL_URL + urllib.parse.quote(full)
               + f"?width=1080&height=1920&nologo=true&model=flux&seed={s}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=120).read()
            if len(data) > 5000:
                dest.write_bytes(data)
                Image.open(dest).verify()
                if _image_ok(dest):
                    return True
                print(f"    kalite denetimi geçemedi (deneme {attempt+1}), yeniden...")
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


# ---------------- hook / cta / müzik ----------------
CTA_TAIL = 2.6          # sonda CTA için eklenen ekstra saniye
HOOK_START, HOOK_END = 0.2, 2.5
MUSIC_VOL = 0.40        # sesin ~12-15 dB altında hafif fon
FONT = gv.FONT

MOOD = {
    "warm": ["adventure", "heartwarming", "funny", "animal"],
    "mystery": ["mystery", "legend", "history", "folktale", "detective"],
    "dreamy": ["fantasy", "space", "scifi", "sci-fi", "magic"],
}


def pick_music(genre):
    g = (genre or "").lower()
    for mood, keys in MOOD.items():
        if any(k in g for k in keys):
            f = ROOT / "assets" / "music" / f"{mood}.mp3"
            return f if f.exists() else None
    f = ROOT / "assets" / "music" / "warm.mp3"
    return f if f.exists() else None


def _wrap(words, max_chars):
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def render_hook_png(text, path):
    """İlk 2 sn'de görünecek büyük, dikkat çekici hook kartı (koyu şeffaf zeminli)."""
    text = text.upper().strip().rstrip(".")
    size, stroke, pad, gap = 104, 11, 46, 18
    lines = _wrap(text.split(), 15) or [text]
    font = ImageFont.truetype(str(FONT), size)
    while size > 54:
        font = ImageFont.truetype(str(FONT), size)
        widths = [font.getbbox(ln, stroke_width=stroke)[2] for ln in lines]
        if max(widths) <= 1000 - 2 * pad:
            break
        size -= 6
    lh = font.getbbox("Ay", stroke_width=stroke)[3]
    tw = max(font.getbbox(ln, stroke_width=stroke)[2] for ln in lines)
    th = lh * len(lines) + gap * (len(lines) - 1)
    img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded(d, [0, 0, img.width, img.height], 40, (0, 0, 0, 150))
    y = pad
    for ln in lines:
        w = font.getbbox(ln, stroke_width=stroke)[2]
        d.text(((img.width - w) / 2, y), ln, font=font, fill=(255, 231, 76, 255),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        y += lh + gap
    img.save(path)
    return img.size


def render_cta_png(text, path):
    """Son karede görünecek CTA/cliffhanger (pill zeminli)."""
    text = text.strip()
    size, stroke, pad = 74, 8, 40
    font = ImageFont.truetype(str(FONT), size)
    while size > 44:
        font = ImageFont.truetype(str(FONT), size)
        if font.getbbox(text, stroke_width=stroke)[2] <= 1000 - 2 * pad:
            break
        size -= 5
    bb = font.getbbox(text, stroke_width=stroke)
    tw, th = bb[2], bb[3]
    img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded(d, [0, 0, img.width, img.height], img.height // 2, (200, 30, 40, 220))
    d.text((pad, pad - bb[1]), text, font=font, fill=(255, 255, 255, 255),
           stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    img.save(path)
    return img.size


def render_watermark_png(handle, path):
    """Kanal markası: küçük, yarı saydam filigran (üst-orta)."""
    size, stroke, pad = 40, 4, 12
    font = ImageFont.truetype(str(FONT), size)
    bb = font.getbbox(handle, stroke_width=stroke)
    img = Image.new("RGBA", (bb[2] + pad * 2, bb[3] + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad, pad - bb[1]), handle, font=font, fill=(255, 255, 255, 175),
           stroke_width=stroke, stroke_fill=(0, 0, 0, 130))
    img.save(path)
    return img.size


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
    style = cfg.get("signature_style") or story.get("style", "cinematic storybook illustration, dramatic lighting")
    character = story.get("character", "")
    handle = cfg.get("channel_handle", "").strip()
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
    # her üretimde rastgele seed -> aynı hikaye tekrar gelse bile görseller farklı çıkar
    base_seed = random.randint(1000, 900000)
    segs, last_img = [], None
    for i, (mp3, dur, gwords, sc) in enumerate(kept):
        scene_img = sc["image"].replace("the character", character) if character else sc["image"]
        prompt = f"{scene_img}. Art style: {style}."
        img = WORK / f"img_{i:02d}.jpg"
        ok = gen_image(prompt, img, base_seed + i)
        last_img = img
        seg = ken_burns(img, dur, WORK / f"seg_{i:02d}.mp4", zoom_in=(i % 2 == 0))
        segs.append(seg)
        print(f"  sahne {i+1}/{len(kept)}: {'AI resim' if ok else 'gradyan yedek'}")

    # CTA kuyruğu: son resmi CTA_TAIL saniye daha tut
    if last_img is not None:
        segs.append(ken_burns(last_img, CTA_TAIL, WORK / "seg_cta.mp4", zoom_in=True))
    video_total = min(total + CTA_TAIL, 59.5)

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

    # hook + cta + filigran kartları + müzik seçimi
    hook_text = (story.get("hook") or " ".join(seo._clean(story["title"]).split()[:6])).strip()
    cta_text = (story.get("cta") or "Follow for daily stories").strip()
    hook_png = WORK / "hook.png"; hw, hh = render_hook_png(hook_text, hook_png)
    cta_png = WORK / "cta.png"; cw, ch = render_cta_png(cta_text, cta_png)
    use_wm = bool(handle) and handle != "@YourChannel"
    if use_wm:
        wm_png = WORK / "wm.png"; ww, wh = render_watermark_png(handle, wm_png)
    music = pick_music(story.get("genre"))

    # 5) montaj: bg + altyazı + hook + cta + filigran + (ses + müzik)
    inputs = ["-i", str(bg)]
    for (p, *_rest) in cap_imgs:
        inputs += ["-i", str(p)]
    hook_idx = 1 + len(cap_imgs)
    cta_idx = hook_idx + 1
    inputs += ["-i", str(hook_png), "-i", str(cta_png)]
    if use_wm:
        wm_idx = cta_idx + 1
        inputs += ["-i", str(wm_png)]
        voice_idx = wm_idx + 1
    else:
        voice_idx = cta_idx + 1
    inputs += ["-i", str(voice_all)]
    music_idx = voice_idx + 1
    if music:
        inputs += ["-i", str(music)]

    fc, last = [], "0:v"
    for k, (p, w, h, cs, ce) in enumerate(cap_imgs):
        x = int((W - w) / 2); y = int(CAP_Y - h / 2)
        out = f"v{k}"
        fc.append(f"[{last}][{k+1}:v]overlay={x}:{y}:enable='between(t,{cs:.3f},{ce:.3f})'[{out}]")
        last = out
    # hook (üst-orta, ilk saniyeler)
    hx = int((W - hw) / 2); hy = int(0.24 * H)
    fc.append(f"[{last}][{hook_idx}:v]overlay={hx}:{hy}:enable='between(t,{HOOK_START},{HOOK_END})'[vh]")
    # cta (orta, sonda)
    cta_start = max(0.0, total - 0.6)
    cx = int((W - cw) / 2); cy = int(0.50 * H - ch / 2)
    fc.append(f"[vh][{cta_idx}:v]overlay={cx}:{cy}:enable='between(t,{cta_start:.2f},{video_total:.2f})'[vc]")
    # filigran (üst, tüm video)
    if use_wm:
        wx = int((W - ww) / 2); wy = int(0.045 * H)
        fc.append(f"[vc][{wm_idx}:v]overlay={wx}:{wy}[vout]")
    else:
        fc.append("[vc]null[vout]")

    # ses: konuşma + hafif müzik (son 1.2 sn fade out, taşmaya karşı limiter)
    if music:
        fc.append(
            f"[{music_idx}:a]volume={MUSIC_VOL},afade=t=out:st={max(0.1, video_total-1.2):.2f}:d=1.2[mus];"
            f"[{voice_idx}:a][mus]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
            f"alimiter=limit=0.95[aout]")
        amap = "[aout]"
    else:
        amap = f"{voice_idx}:a"

    filter_complex = ";".join(fc)
    OUT.mkdir(exist_ok=True)
    final = OUT / "short.mp4"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
           "-map", "[vout]", "-map", amap,
           "-t", f"{video_total:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-r", str(FPS), str(final)]
    r = gv.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not final.exists():
        print("MONTAJ HATASI:\n", (r.stderr or "")[-1800:]); return 1

    meta = seo.build_seo_meta(story, cfg)
    meta["series"] = story.get("series", "")
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    # TikTok / Reels için hazır başlık (elle cross-post için)
    (OUT / "tiktok.txt").write_text(seo.build_short_caption(story), encoding="utf-8")
    print(f"BİTTİ -> {final}  ({gv.ffprobe_duration(final):.1f} sn)")
    print("Başlık:", meta["title"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
