#!/usr/bin/env python3
"""
Telifsiz motorspor stok kliplerinden dikey (9:16) hızlı-kesim montaj üretir.
Kaynaklar: Pexels + Pixabay (atıf gerekmez, ticari serbest).
Konuşma yok -> global. Enerjik müzik + hook + ilerleme çubuğu + doğru etiketler.
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_video as gv        # noqa: E402
import generate_story as gs        # noqa: E402
import seo                         # noqa: E402
import fetch_clips                 # noqa: E402

ROOT = gv.ROOT
CONFIG = gv.CONFIG
BANK = ROOT / "content" / "motorsport_topics.json"
STATE = ROOT / "state" / "motorsport_progress.json"
OUT = gv.OUT
WORK = gv.WORK
W, H, FPS = gv.W, gv.H, gv.FPS

SEG = 3.6            # her klip parçası (sn) — hızlı kesim
MUSIC_VOL = 0.9

VERTICAL = (
    "split[a][b];"
    "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20[bg];"
    "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
    "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30"
)


def to_vertical_segment(clip, out_mp4):
    """Klibi ~SEG sn dikey parçaya çevir (ses at)."""
    try:
        dur = gv.ffprobe_duration(clip)
    except Exception:
        return None
    if dur < 1.2:
        return None
    start = min(1.0, dur * 0.15)
    seg = min(SEG, max(1.0, dur - start - 0.1))
    r = gv.run(["ffmpeg", "-y", "-ss", f"{start:.2f}", "-i", str(clip), "-t", f"{seg:.2f}",
                "-vf", VERTICAL, "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", str(out_mp4)], capture_output=True, text=True)
    if r.returncode != 0 or not out_mp4.exists():
        return None
    return out_mp4


def build_meta(topic, cfg):
    title = seo.build_title(topic)
    hashtags = " ".join(seo.build_hashtags(topic))
    q = (topic.get("comment_q") or "Which one is the best?").strip()
    cta = (topic.get("cta") or "Follow for more").strip()
    desc = (
        f"{seo._clean(topic['title'])} 🏁\n\n"
        f"💬 {q}\n"
        f"👉 {cta} — new motorsport edits daily!\n"
        f"🔔 Like & subscribe for more.\n\n"
        f"Footage: Pexels & Pixabay (free license, no attribution required).\n\n"
        f"{hashtags}"
    )
    tags, seen, total = [], set(), 0
    base = ["motorsport", "racing", "cars", "speed", "race car", "fast cars", "car edit",
            "motorsport edit", "racing shorts", "cars shorts", "supercar"]
    for t in seo.build_tags(topic) + base:
        t = t.strip().lower()
        if not t or t in seen or total + len(t) + 1 > 480:
            continue
        seen.add(t); tags.append(t); total += len(t) + 1
    return {"title": title, "description": desc, "tags": tags,
            "categoryId": "2",   # Autos & Vehicles
            "privacyStatus": cfg.get("privacyStatus", "public"),
            "madeForKids": bool(cfg.get("madeForKids", False)),
            "defaultLanguage": cfg.get("defaultLanguage", "en"),
            "series": topic.get("id", "")}


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    if not bank:
        print("Motorspor bankası boş!"); return 1
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        state = {"next_index": 0, "made": []}
    idx = int(state.get("next_index", 0)) % len(bank)
    topic = bank[idx]
    print(f"[{idx}] {topic['title']}")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    # 1) telifsiz klipleri indir
    print("  klipler indiriliyor (Pexels + Pixabay)...")
    clips = fetch_clips.fetch_for_queries(topic["queries"], WORK, want=8)
    print(f"  {len(clips)} klip indirildi")
    if len(clips) < 3:
        print("  YETERLİ KLİP YOK (API key eksik ya da sonuç az). İptal."); return 1

    # 2) dikey parçalara çevir
    segs, first_seg = [], None
    for i, c in enumerate(clips):
        s = to_vertical_segment(c, WORK / f"seg_{i:02d}.mp4")
        if s:
            segs.append(s)
            if first_seg is None:
                first_seg = s
    if len(segs) < 3:
        print("  dikey parça üretilemedi. İptal."); return 1
    print(f"  {len(segs)} parça hazır")

    # 3) birleştir
    vlist = WORK / "vlist.txt"
    vlist.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    bg = WORK / "bg.mp4"
    gv.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(vlist),
            "-c", "copy", str(bg)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    video_total = min(gv.ffprobe_duration(bg), 59.5)

    # 4) kartlar
    hook_text = (topic.get("hook") or " ".join(seo._clean(topic["title"]).split()[:5])).strip()
    cta_text = (topic.get("cta") or "Follow for more").strip()
    hook_png = WORK / "hook.png"; hw, hh = gs.render_hook_png(hook_text, hook_png)
    cta_png = WORK / "cta.png"; cw, ch = gs.render_cta_png(cta_text, cta_png)
    handle = cfg.get("channel_handle", "").strip()
    use_wm = bool(handle) and handle != "@YourChannel"
    if use_wm:
        wm_png = WORK / "wm.png"; ww, wh = gs.render_watermark_png(handle, wm_png)
    music = gs.pick_music(topic.get("music_mood") or "warm")

    # 5) montaj
    inputs = ["-i", str(bg), "-i", str(hook_png), "-i", str(cta_png)]
    hook_idx, cta_idx = 1, 2
    nxt = 3
    if use_wm:
        wm_idx = nxt; inputs += ["-i", str(wm_png)]; nxt += 1
    music_idx = nxt
    if music:
        inputs += ["-i", str(music)]

    fc = []
    fc.append(f"[0:v][{hook_idx}:v]overlay={int((W-hw)/2)}:{int(0.20*H)}:enable='between(t,0.2,2.4)'[vh]")
    fc.append(f"[vh][{cta_idx}:v]overlay={int((W-cw)/2)}:{int(0.5*H-ch/2)}:enable='between(t,{video_total-2.6:.2f},{video_total:.2f})'[vc]")
    if use_wm:
        fc.append(f"[vc][{wm_idx}:v]overlay={int((W-ww)/2)}:{int(0.045*H)}[vbar]")
    else:
        fc.append("[vc]null[vbar]")
    fc.append(
        f"[vbar]drawbox=x=0:y=0:w=iw:h=10:color=white@0.22:thickness=fill,"
        f"drawbox=x=0:y=0:w='iw*t/{video_total:.2f}':h=10:color=0xFFE74C@0.95:thickness=fill[vout]")

    if music:
        fc.append(f"[{music_idx}:a]volume={MUSIC_VOL},afade=t=in:st=0:d=0.5,"
                  f"afade=t=out:st={max(0.1, video_total-1.2):.2f}:d=1.2,alimiter=limit=0.95[aout]")
        maps = ["-map", "[vout]", "-map", "[aout]"]
    else:
        maps = ["-map", "[vout]"]

    OUT.mkdir(exist_ok=True)
    final = OUT / "short.mp4"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), *maps,
           "-t", f"{video_total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-r", str(FPS), str(final)]
    r = gv.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not final.exists():
        print("MONTAJ HATASI:\n", (r.stderr or "")[-1800:]); return 1

    meta = build_meta(topic, cfg)
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "tiktok.txt").write_text(
        f"{hook_text} 🏁\n" + " ".join(seo.build_hashtags(topic)[:6]), encoding="utf-8")
    try:
        gs.make_thumbnail(first_seg_frame(first_seg), hook_png, OUT / "thumb.jpg")
    except Exception as e:
        print("kapak atlandı:", str(e)[:80])
    print(f"BİTTİ -> {final}  ({gv.ffprobe_duration(final):.1f} sn)")
    print("Başlık:", meta["title"])
    return 0


def first_seg_frame(seg):
    """İlk segmentten kapak için bir kare çıkar."""
    frame = WORK / "thumb_src.jpg"
    gv.run(["ffmpeg", "-y", "-ss", "0.5", "-i", str(seg), "-frames:v", "1", str(frame)],
           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return frame


if __name__ == "__main__":
    sys.exit(main())
