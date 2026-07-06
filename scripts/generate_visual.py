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

REVEAL_SEC = 3.0          # her reveal ekranda kaç sn
TAIL_SEC = 2.6            # sonda yorum sorusu kartı
MUSIC_VOL = 0.85         # konuşma yok -> müzik ana ses
LABEL_Y = int(H * 0.82)   # etiket dikey konumu (alt)


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


def build_meta(theme, cfg):
    title = seo.build_title(theme)
    tags = seo.build_tags(theme)
    hashtags = " ".join(seo.build_hashtags(theme))
    q = (theme.get("comment_q") or "Which one is your favorite?").strip()
    desc = f"{seo._clean(theme['title'])} 🎬\n\n{q}\n👉 Follow for more!\n\n{hashtags}"
    return {"title": title, "description": desc, "tags": tags,
            "categoryId": str(cfg.get("categoryId", "24")),
            "privacyStatus": cfg.get("privacyStatus", "public"),
            "madeForKids": bool(cfg.get("madeForKids", False)),
            "defaultLanguage": cfg.get("defaultLanguage", "en"),
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
        segs.append(gs.ken_burns(img, REVEAL_SEC, WORK / f"seg_{i:02d}.mp4", zoom_in=(i % 2 == 0)))
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
        inputs += ["-i", str(music)]

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

    if music:
        fc.append(
            f"[{music_idx}:a]volume={MUSIC_VOL},afade=t=in:st=0:d=0.6,"
            f"afade=t=out:st={max(0.1, video_total-1.2):.2f}:d=1.2,alimiter=limit=0.95[aout]")
        amap = "[aout]"
        maps = ["-map", "[vout]", "-map", amap]
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
        f"{hook_text} ✨\n{q_text}\n" + " ".join(seo.build_hashtags(theme)[:6]), encoding="utf-8")
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
