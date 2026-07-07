#!/usr/bin/env python3
"""
DİLSİZ / GLOBAL viral görsel reveal üretici.

Akış:
  tema bankasından sıradaki temayı al (ör. "Her burç bir savaşçı olarak")
  -> her reveal için ÜCRETSİZ AI görsel üret (Pollinations)
  -> Ken Burns hareketi + etiket (label) yak
  -> hook + ilerleme çubuğu + fon müzik (konuşma YOK, global)
  -> son karede yorum-tetikleyici soru
  -> 9:16, ~28-32 sn

TTS yok = her ülkeden izlenir. generate_story/generate_video yardımcıları yeniden kullanılır.
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_video as gv        # noqa: E402  run/ffprobe/W/H/FPS/sabitler
import generate_story as gs        # noqa: E402  gen_image/ken_burns/render_*/pick_music
import seo                         # noqa: E402

ROOT = gv.ROOT
CONFIG = gv.CONFIG
BANK = ROOT / "content" / "visual_themes.json"
STATE = ROOT / "state" / "visual_progress.json"
OUT = gv.OUT
WORK = gv.WORK
FONT = gv.FONT
W, H, FPS = gv.W, gv.H, gv.FPS

REVEAL_SEC = 1.9          # her reveal ekranda kaç sn (hızlı tempo = retention)
TAIL_SEC = 2.6            # sonda yorum sorusu kartı
MUSIC_VOL = 0.8          # konuşma yok -> müzik ana ses
WHOOSH_VOL = 0.9          # geçiş sesi
LABEL_Y = int(H * 0.82)   # etiket dikey konumu (alt)
SFX = gv.ROOT / "assets" / "sfx" / "whoosh.mp3"


def build_whoosh_track(times, dest, total):
    """Her reveal anına whoosh yerleştirilmiş bir ses parçası üretir."""
    if not SFX.exists() or not times:
        return None
    inputs = []
    for _ in times:
        inputs += ["-i", str(SFX)]
    fc = []
    for i, t in enumerate(times):
        ms = int(t * 1000)
        fc.append(f"[{i}:a]adelay={ms}|{ms}[w{i}]")
    fc.append("".join(f"[w{i}]" for i in range(len(times))) +
              f"amix=inputs={len(times)}:normalize=0[wt]")
    gv.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
            "-map", "[wt]", "-t", f"{total:.3f}", str(dest)],
           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def render_label_png(text, path):
    """Reveal etiketi: alt-orta, kalın, koyu pill zeminli."""
    text = text.upper().strip()
    size, stroke, pad = 92, 10, 40
    font = ImageFont.truetype(str(FONT), size)
    while size > 50:
        font = ImageFont.truetype(str(FONT), size)
        if font.getbbox(text, stroke_width=stroke)[2] <= W - 140:
            break
        size -= 6
    bb = font.getbbox(text, stroke_width=stroke)
    img = Image.new("RGBA", (bb[2] + pad * 2, bb[3] + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, img.width, img.height], radius=32, fill=(0, 0, 0, 150))
    d.text((pad, pad - bb[1]), text, font=font, fill=(255, 255, 255, 255),
           stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    img.save(path)
    return img.size


# kategori -> YouTube categoryId (içeriğe uygun; anahtar kelimeler İngilizce+Türkçe eşleşir)
CAT_YT = [
    (("finance", "wealth", "money", "finans", "servet"), "27"),      # Education
    (("science", "nature", "world", "space", "doga", "doğa"), "28"), # Science & Tech
    (("motiv", "mindset", "zihniyet", "self"), "22"),                # People & Blogs
    (("animal", "pet"), "15"),                                       # Pets & Animals
    (("kid", "cartoon", "child", "cocuk", "çocuk"), "1"),            # Film & Animation
    (("music",), "10"),
]

# İçerik-uyumlu hashtag havuzu — TAMAMEN İNGİLİZCE / GLOBAL
HASH_UNIVERSAL = ["#shorts", "#viral", "#fyp", "#foryou", "#shortsfeed", "#trending", "#reveal"]
HASH_CAT = [
    (("finance", "wealth", "money", "finans", "servet"), ["#money", "#wealth", "#luxury"]),
    (("zodiac", "astro", "burc", "burç"), ["#zodiac", "#astrology", "#zodiacsigns"]),
    (("luxury", "lifestyle", "luks", "lüks", "rich"), ["#luxury", "#luxurylifestyle", "#rich"]),
    (("entertain", "curio", "fun", "eglence", "eğlence"), ["#fun", "#whichoneareyou", "#aesthetic"]),
    (("motiv", "mindset", "zihniyet", "self"), ["#motivation", "#mindset", "#success"]),
    (("nature", "world", "space", "doga", "doğa"), ["#nature", "#satisfying", "#space"]),
    (("aesthetic", "color", "estetik", "renk"), ["#aesthetic", "#aestheticedit", "#colors"]),
    (("myth", "legend", "efsane", "mitoloji", "fantasy"), ["#mythology", "#fantasy", "#legend"]),
]
TAGS_UNIVERSAL = ["shorts", "viral", "fyp", "for you", "reveal", "which one are you",
                  "satisfying", "aesthetic", "trending shorts", "ai art"]


def _cat(theme):
    return (theme.get("category") or "").lower()


def yt_category(theme, cfg):
    cat = _cat(theme)
    for keys, cid in CAT_YT:
        if any(k in cat for k in keys):
            return cid
    return str(cfg.get("categoryId", "24"))   # varsayılan Entertainment


def build_hashtags(theme):
    """En fazla 15, ilk 3 en güçlü, tümü İngilizce, içeriğe uygun."""
    cat = _cat(theme)
    tags = ["#shorts"]
    for keys, hs in HASH_CAT:
        if any(k in cat for k in keys):
            tags += hs
            break
    for h in HASH_UNIVERSAL:
        if h.lower() not in [x.lower() for x in tags]:
            tags.append(h)
    return tags[:15]


def build_tags(theme):
    cat = _cat(theme)
    cat_words = [k for keys, _ in HASH_CAT for k in keys if k in cat and k.isascii()][:2]
    raw = (list(theme.get("tags", [])) + TAGS_UNIVERSAL + cat_words
           + [r["label"].lower() for r in theme.get("reveals", [])])
    out, seen, total = [], set(), 0
    for t in raw:
        t = str(t).strip().lower()
        if not t or t in seen or total + len(t) + 1 > 480:
            continue
        seen.add(t); out.append(t); total += len(t) + 1
    return out


def build_meta(theme, cfg):
    title = seo.build_title(theme)
    hashtags = " ".join(build_hashtags(theme))
    q = (theme.get("comment_q") or "Which one is your favorite?").strip()
    cta = (theme.get("cta") or "Follow for more").strip()
    labels = ", ".join(r["label"] for r in theme.get("reveals", [])[:8])
    desc = (
        f"{seo._clean(theme['title'])} ✨\n\n"
        f"💬 {q}\n"
        f"👉 {cta} — new reveals every day!\n"
        f"🔔 Like & subscribe so you never miss one.\n\n"
        f"In this video: {labels}.\n\n"
        f"{hashtags}"
    )
    return {"title": title, "description": desc, "tags": build_tags(theme),
            "categoryId": yt_category(theme, cfg),
            "privacyStatus": cfg.get("privacyStatus", "public"),
            "madeForKids": bool(cfg.get("madeForKids", False)),
            "defaultLanguage": "en",
            "series": theme.get("id", "")}


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    if not bank:
        print("Tema bankası boş!"); return 1
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        state = {"next_index": 0, "made": []}
    idx = int(state.get("next_index", 0)) % len(bank)
    theme = bank[idx]
    style = theme.get("style", "hyper-detailed cinematic fantasy portrait, dramatic lighting, epic, vibrant")
    reveals = theme["reveals"][:10]
    print(f"[{idx}] {theme['title']}  ({len(reveals)} reveal)")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    # 1) her reveal: AI görsel + Ken Burns segmenti + etiket
    base_seed = random.randint(1000, 900000)
    segs, labels, first_img, last_img = [], [], None, None
    for i, rv in enumerate(reveals):
        prompt = f"{rv['image']}. Art style: {style}."
        img = WORK / f"img_{i:02d}.jpg"
        gs.gen_image(prompt, img, base_seed + i)
        if first_img is None:
            first_img = img
        last_img = img
        segs.append(gs.ken_burns(img, REVEAL_SEC, WORK / f"seg_{i:02d}.mp4",
                                 zoom_in=(i % 2 == 0), flash=True))
        lp = WORK / f"lbl_{i:02d}.png"
        lw, lh = render_label_png(rv["label"], lp)
        labels.append((lp, lw, lh, i * REVEAL_SEC, (i + 1) * REVEAL_SEC))
        print(f"  reveal {i+1}/{len(reveals)}: {rv['label']}")

    total = len(reveals) * REVEAL_SEC
    # son kare tut (yorum sorusu kartı için)
    if last_img is not None:
        segs.append(gs.ken_burns(last_img, TAIL_SEC, WORK / "seg_tail.mp4", zoom_in=True))
    video_total = min(total + TAIL_SEC, 59.5)

    vlist = WORK / "vlist.txt"
    vlist.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    bg = WORK / "bg.mp4"
    gv.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(vlist),
            "-c", "copy", str(bg)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # kartlar
    hook_text = (theme.get("hook") or " ".join(seo._clean(theme["title"]).split()[:5])).strip()
    q_text = (theme.get("comment_q") or "Which one are you?").strip()
    cta_text = (theme.get("cta") or "Follow for more").strip()
    hook_png = WORK / "hook.png"; hw, hh = gs.render_hook_png(hook_text, hook_png)
    q_png = WORK / "q.png"; qw, qh = gs.render_hook_png(q_text, q_png)
    cta_png = WORK / "cta.png"; cw, ch = gs.render_cta_png(cta_text, cta_png)
    handle = cfg.get("channel_handle", "").strip()
    use_wm = bool(handle) and handle != "@YourChannel"
    if use_wm:
        wm_png = WORK / "wm.png"; ww, wh = gs.render_watermark_png(handle, wm_png)
    music = gs.pick_music(theme.get("music_mood") or "dreamy")
    reveal_times = [i * REVEAL_SEC for i in range(len(reveals))]
    whoosh_track = build_whoosh_track(reveal_times, WORK / "whoosh.wav", video_total)

    # 2) montaj
    inputs = ["-i", str(bg)]
    for (p, *_r) in labels:
        inputs += ["-i", str(p)]
    n_lbl = len(labels)
    hook_idx = 1 + n_lbl
    q_idx = hook_idx + 1
    cta_idx = q_idx + 1
    inputs += ["-i", str(hook_png), "-i", str(q_png), "-i", str(cta_png)]
    nxt = cta_idx + 1
    if use_wm:
        wm_idx = nxt; inputs += ["-i", str(wm_png)]; nxt += 1
    music_idx = nxt
    if music:
        inputs += ["-i", str(music)]; nxt += 1
    whoosh_idx = nxt
    if whoosh_track:
        inputs += ["-i", str(whoosh_track)]

    fc, last = [], "0:v"
    for k, (p, lw, lh, s, e) in enumerate(labels):
        x = int((W - lw) / 2); y = int(LABEL_Y - lh / 2)
        out = f"l{k}"
        fc.append(f"[{last}][{k+1}:v]overlay={x}:{y}:enable='between(t,{s:.2f},{e:.2f})'[{out}]")
        last = out
    # hook (üst, ilk saniyeler)
    fc.append(f"[{last}][{hook_idx}:v]overlay={int((W-hw)/2)}:{int(0.20*H)}:enable='between(t,0.2,2.4)'[vh]")
    # yorum sorusu (orta, sonda)
    fc.append(f"[vh][{q_idx}:v]overlay={int((W-qw)/2)}:{int(0.40*H-qh/2)}:enable='between(t,{total-0.4:.2f},{video_total:.2f})'[vq]")
    # cta (alt-orta, sonda)
    fc.append(f"[vq][{cta_idx}:v]overlay={int((W-cw)/2)}:{int(0.62*H)}:enable='between(t,{total-0.4:.2f},{video_total:.2f})'[vc]")
    # filigran
    if use_wm:
        fc.append(f"[vc][{wm_idx}:v]overlay={int((W-ww)/2)}:{int(0.045*H)}[vbar]")
    else:
        fc.append("[vc]null[vbar]")
    # ilerleme çubuğu
    fc.append(
        f"[vbar]drawbox=x=0:y=0:w=iw:h=10:color=white@0.22:thickness=fill,"
        f"drawbox=x=0:y=0:w='iw*t/{video_total:.2f}':h=10:color=0xFFE74C@0.95:thickness=fill[vout]")

    aud = []
    if music:
        fc.append(f"[{music_idx}:a]volume={MUSIC_VOL},afade=t=in:st=0:d=0.6,"
                  f"afade=t=out:st={max(0.1, video_total-1.2):.2f}:d=1.2[amus]")
        aud.append("[amus]")
    if whoosh_track:
        fc.append(f"[{whoosh_idx}:a]volume={WHOOSH_VOL}[awh]")
        aud.append("[awh]")
    if len(aud) >= 2:
        fc.append(f"{''.join(aud)}amix=inputs={len(aud)}:normalize=0,alimiter=limit=0.95[aout]")
        maps = ["-map", "[vout]", "-map", "[aout]"]
    elif len(aud) == 1:
        fc.append(f"{aud[0]}alimiter=limit=0.95[aout]")
        maps = ["-map", "[vout]", "-map", "[aout]"]
    else:
        maps = ["-map", "[vout]"]

    filter_complex = ";".join(fc)
    OUT.mkdir(exist_ok=True)
    final = OUT / "short.mp4"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex, *maps,
           "-t", f"{video_total:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-r", str(FPS), str(final)]
    r = gv.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not final.exists():
        print("MONTAJ HATASI:\n", (r.stderr or "")[-1800:]); return 1

    meta = build_meta(theme, cfg)
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "tiktok.txt").write_text(
        f"{hook_text} ✨\n{q_text}\n" + " ".join(build_hashtags(theme)[:6]), encoding="utf-8")
    try:
        if first_img and first_img.exists():
            gs.make_thumbnail(first_img, hook_png, OUT / "thumb.jpg")
    except Exception as e:
        print("kapak atlandı:", str(e)[:80])
    print(f"BİTTİ -> {final}  ({gv.ffprobe_duration(final):.1f} sn)")
    print("Başlık:", meta["title"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
