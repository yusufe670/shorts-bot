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

TARGET_SEC = 17.0    # hedef toplam süre (~15-20 sn)
MAX_CLIPS = 5        # kısa video için az klip
MUSIC_VOL = 0.9

VERTICAL = (
    "split[a][b];"
    "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20[bg];"
    "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
    "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,"
    # sinematik renk: güçlü kontrast (beyaz duman / koyu asfalt) + doygunluk + keskinlik
    "eq=contrast=1.22:saturation=1.4:gamma=0.93,vibrance=intensity=0.25,"
    "curves=all='0/0 0.25/0.16 0.75/0.88 1/1',"
    "unsharp=5:5:0.9:5:5:0.0"
)
# klip başına hız rampası deseni (slow-mo + hızlandırma -> dinamizm)
SPEEDS = [1.0, 0.8, 1.25, 0.85, 1.2]


def pick_lib_music():
    """Müzik kütüphanesinden (lib/) rastgele bir parça seç."""
    lib = sorted((ROOT / "assets" / "music" / "lib").glob("*.mp3"))
    if lib:
        return random.choice(lib)
    return None   # müzik yoksa sessiz


def make_whoosh(path):
    """Geçiş whoosh sesi (filtreli gürültü — kesimlerde vurgu)."""
    gv.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.5:c=pink:a=0.8",
            "-af", "highpass=f=400,lowpass=f=7000,afade=t=in:st=0:d=0.12,"
            "afade=t=out:st=0.18:d=0.32,volume=0.7", str(path)],
           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def motion_score(clip):
    """Kaba hareket skoru (kare farkı ortalaması) — en hareketli klip başa gelsin."""
    import re
    r = gv.run(["ffmpeg", "-hide_banner", "-ss", "0.3", "-t", "3", "-i", str(clip),
                "-vf", "scale=160:90,tblend=all_mode=difference,signalstats,"
                       "metadata=print:key=lavfi.signalstats.YAVG",
                "-an", "-f", "null", "-"], capture_output=True, text=True)
    vals = [float(x) for x in re.findall(r"YAVG=([\d.]+)", r.stderr or "")]
    return sum(vals) / len(vals) if vals else 0.0


def _has_audio(clip):
    r = gv.run(["ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(clip)],
               capture_output=True, text=True)
    return "audio" in (r.stdout or "")


def to_vertical_segment(clip, out_mp4, seg_target=3.5, speed=1.0):
    """Dikey + renk tonlu + hız rampalı parça. GERÇEK klip sesini korur (motor/lastik)."""
    try:
        dur = gv.ffprobe_duration(clip)
    except Exception:
        return None
    if dur < 1.2:
        return None
    start = min(1.0, dur * 0.12)
    src_len = seg_target * speed
    if start + src_len > dur - 0.05:
        src_len = max(0.8, dur - start - 0.05)
    out_dur = src_len / speed
    vfilter = f"[0:v]setpts=PTS/{speed:.3f},{VERTICAL}[v]"
    if _has_audio(clip):
        atempo = min(2.0, max(0.5, speed))
        fc = (f"{vfilter};[0:a]atempo={atempo:.3f},volume=1.6,aresample=44100,"
              f"aformat=channel_layouts=stereo[a]")
        cmd = ["ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{src_len:.2f}", "-i", str(clip),
               "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
               "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-ar", "44100", str(out_mp4)]
    else:
        cmd = ["ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{src_len:.2f}", "-i", str(clip),
               "-f", "lavfi", "-t", f"{out_dur:.2f}", "-i", "anullsrc=r=44100:cl=stereo",
               "-filter_complex", vfilter, "-map", "[v]", "-map", "1:a",
               "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-ar", "44100", "-shortest", str(out_mp4)]
    r = gv.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out_mp4.exists():
        return None
    return out_mp4


# En etkili motorspor + phonk/araba-kültürü hashtag'leri (bu kitlenin kullandığı)
MOTO_HASHTAGS = ("#shorts #cars #car #supercar #racing #jdm #drift #phonk "
                 "#caredit #carculture #speed #fyp #viral #fastcars #cargram")
MOTO_TAGS = ["cars", "car", "supercar", "racing", "motorsport", "car edit", "phonk",
             "jdm", "drift", "car culture", "speed", "fast cars", "car lovers",
             "sports car", "cars shorts", "car edit phonk", "car video", "cargram"]


def build_meta(topic, cfg):
    title = seo.build_title(topic)
    q = (topic.get("comment_q") or "Which one is the best?").strip()
    # temiz, evrensel açıklama
    desc = f"{seo._clean(topic['title'])}\n\n{q}\n\n{MOTO_HASHTAGS}"
    # temiz etiketler (konu + motorspor)
    tags, seen, total = [], set(), 0
    for t in [x.lower() for x in topic.get("tags", [])] + MOTO_TAGS:
        t = t.strip().lower()
        if not t or t in seen or total + len(t) + 1 > 460:
            continue
        seen.add(t); tags.append(t); total += len(t) + 1
    return {"title": title, "description": desc, "tags": tags,
            "categoryId": "2",   # Autos & Vehicles
            "privacyStatus": cfg.get("privacyStatus", "private"),
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

    # 1) telifsiz GERÇEK klipleri indir (CGI/animasyon fetch_clips'te elenir)
    print("  klipler indiriliyor (Pexels + Pixabay, gerçek çekim)...")
    clips = fetch_clips.fetch_for_queries(topic["queries"], WORK, want=MAX_CLIPS + 2)
    if len(clips) < 3:
        print("  YETERLİ KLİP YOK (API key eksik ya da sonuç az). İptal."); return 1
    # en hareketli klipleri seç ve en hareketliyi BAŞA koy (kaos ilk karede)
    clips.sort(key=motion_score, reverse=True)
    clips = clips[:MAX_CLIPS]
    print(f"  {len(clips)} klip (hareket sıralı, en aksiyonlu başta)")

    # 2) dikey parçalara çevir (kısa video: hedef ~17sn / klip sayısı)
    seg_len = min(4.8, max(3.0, TARGET_SEC / max(1, len(clips))))
    segs, first_seg = [], None
    for i, c in enumerate(clips):
        spd = SPEEDS[i % len(SPEEDS)]   # slow-mo / hızlandırma rampası
        s = to_vertical_segment(c, WORK / f"seg_{i:02d}.mp4", seg_len, speed=spd)
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
    # geçiş whoosh'ları için kesim zamanları
    cut_times, acc = [], 0.0
    for s in segs[:-1]:
        acc += gv.ffprobe_duration(s)
        if 0.3 < acc < video_total - 0.4:
            cut_times.append(acc)
    whoosh = WORK / "whoosh.wav"
    make_whoosh(whoosh)

    # 4) kartlar
    hook_text = (topic.get("hook") or " ".join(seo._clean(topic["title"]).split()[:5])).strip()
    cta_text = (topic.get("cta") or "Follow for more").strip()
    hook_png = WORK / "hook.png"; hw, hh = gs.render_hook_png(hook_text, hook_png)
    cta_png = WORK / "cta.png"; cw, ch = gs.render_cta_png(cta_text, cta_png)
    handle = cfg.get("channel_handle", "").strip()
    use_wm = bool(handle) and handle != "@YourChannel"
    if use_wm:
        wm_png = WORK / "wm.png"; ww, wh = gs.render_watermark_png(handle, wm_png)
    # her videoya kütüphaneden RASTGELE enerjik beat (add_music=false ise sessiz)
    music = pick_lib_music() if cfg.get("add_music", True) else None

    # 5) montaj
    inputs = ["-i", str(bg), "-i", str(hook_png), "-i", str(cta_png)]
    hook_idx, cta_idx = 1, 2
    nxt = 3
    if use_wm:
        wm_idx = nxt; inputs += ["-i", str(wm_png)]; nxt += 1
    music_idx = nxt
    if music:
        inputs += ["-i", str(music)]; nxt += 1
    whoosh_idx = nxt
    if music and cut_times:
        inputs += ["-i", str(whoosh)]; nxt += 1

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
        # müzik (loudnorm ile tutarlı) + GERÇEK motor sesi + whoosh geçişler
        fc.append(f"[{music_idx}:a]loudnorm=I=-11:TP=-1.0,afade=t=in:st=0:d=0.5,"
                  f"afade=t=out:st={max(0.1, video_total-1.2):.2f}:d=1.2[m]")
        fc.append("[0:a]aformat=channel_layouts=stereo,highpass=f=110,volume=0.95,"
                  "alimiter=limit=0.9[eng]")   # klibin gerçek sesi (motor/lastik)
        amix_in = ["[m]", "[eng]"]
        if cut_times:
            fc.append(f"[{whoosh_idx}:a]asplit={len(cut_times)}"
                      + "".join(f"[w{k}]" for k in range(len(cut_times))))
            for k, t in enumerate(cut_times):
                ms = int(t * 1000)
                fc.append(f"[w{k}]adelay={ms}|{ms}[wd{k}]")
                amix_in.append(f"[wd{k}]")
        fc.append(f"{''.join(amix_in)}amix=inputs={len(amix_in)}:normalize=0,"
                  f"alimiter=limit=0.95[aout]")
        maps = ["-map", "[vout]", "-map", "[aout]"]
    else:
        maps = ["-map", "[vout]", "-map", "0:a?"]

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
    # Uygulamadan yüklerken kopyala-yapıştır caption (temiz, evrensel)
    (OUT / "caption.txt").write_text(
        f"{seo._clean(topic['title'])}\n\n{(topic.get('comment_q') or '').strip()}\n\n{MOTO_HASHTAGS}",
        encoding="utf-8")
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
