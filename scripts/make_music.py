#!/usr/bin/env python3
"""
Telifsiz, enerjik beat kütüphanesi üretir (phonk/motorspor tarzı: kick+808+hat+karanlık melodi).
assets/music/track_00.mp3 ... track_NN.mp3 -> generate_motorsport rastgele seçer.
Bir kez: python scripts/make_music.py
"""
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUS = ROOT / "assets" / "music"
LIB = MUS / "lib"
TMP = MUS / "_tmp"
for d in (LIB, TMP):
    d.mkdir(parents=True, exist_ok=True)

BARS = 16          # kaç bar döngü
MINOR = [0, 3, 5, 7, 10]   # minör pentatonik (uyumsuz çıkmaz)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def note_hz(root, semis):
    return root * (2 ** (semis / 12.0))


def make_sample_kick(path, step):
    # kick: düşük sinüs + hızlı düşüş (thump)
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=55:duration={step:.3f}",
         "-af", f"afade=t=out:st=0:d={step*0.9:.3f},volume=1.4", str(path)])


def make_sample_hat(path, step):
    # hat: kısa beyaz gürültü, tiz, hızlı düşüş
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anoisesrc=d={step:.3f}:c=pink:a=0.4",
         "-af", f"highpass=f=7000,afade=t=out:st=0:d={step*0.5:.3f},volume=0.5", str(path)])


def make_sample_silence(path, step):
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={step:.3f}", str(path)])


def make_note(path, hz, step, vol=0.5, decay=0.85):
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={hz:.2f}:duration={step:.3f}",
         "-af", f"afade=t=in:st=0:d=0.005,afade=t=out:st={step*decay:.3f}:d={step*(1-decay)+0.01:.3f},"
         f"volume={vol}", str(path)])


def element_track(slots, tmp_prefix, total, i):
    """slots: her 16-adımlık bar için sample path listesi (None=sessiz). -> döngülü tam parça."""
    barlist = TMP / f"{tmp_prefix}_{i}_bar.txt"
    barlist.write_text("".join(f"file '{s.as_posix()}'\n" for s in slots), encoding="utf-8")
    bar = TMP / f"{tmp_prefix}_{i}_bar.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(barlist), "-c", "copy", str(bar)])
    full = TMP / f"{tmp_prefix}_{i}_full.wav"
    run(["ffmpeg", "-y", "-stream_loop", str(BARS - 1), "-i", str(bar), str(full)])
    return full


# desen varyasyonları (16 adım)
KICKS = [
    [1,0,0,0, 0,0,1,0, 0,0,0,0, 1,0,0,0],
    [1,0,0,0, 1,0,0,0, 1,0,0,0, 1,0,0,0],
    [1,0,0,1, 0,0,1,0, 0,1,0,0, 1,0,0,0],
]
HATS = [
    [0,0,1,0, 0,0,1,0, 0,0,1,0, 0,0,1,1],
    [0,1,0,1, 0,1,0,1, 0,1,0,1, 0,1,1,1],
]
BASSLINES = [
    [0,None,None,None, 0,None,None,None, 3,None,None,None, 0,None,None,None],
    [0,None,None,0, None,None,7,None, None,None,5,None, 0,None,None,None],
]
LEADS = [
    [0,None,3,None, 5,None,3,None, 7,None,5,None, 3,None,0,None],
    [7,None,None,5, None,3,None,None, 5,None,3,None, None,0,None,None],
    [0,None,7,None, None,5,None,3, None,None,7,None, 5,None,3,None],
]


def build_track(i, bpm, root_hz, kick_p, hat_p, bass_p, lead_p):
    step = 60.0 / bpm / 4.0
    kick = TMP / f"kick_{i}.wav"; make_sample_kick(kick, step)
    hat = TMP / f"hat_{i}.wav"; make_sample_hat(hat, step)
    sil = TMP / f"sil_{i}.wav"; make_sample_silence(sil, step)

    # pitched notalar (bass 1 oktav aşağı, lead orta)
    bass_notes, lead_notes = {}, {}
    for off in set(x for x in bass_p if x is not None):
        p = TMP / f"b_{i}_{off}.wav"; make_note(p, note_hz(root_hz / 2, MINOR[off % len(MINOR)]), step, vol=0.55, decay=0.9)
        bass_notes[off] = p
    for off in set(x for x in lead_p if x is not None):
        p = TMP / f"l_{i}_{off}.wav"; make_note(p, note_hz(root_hz, MINOR[off % len(MINOR)]), step, vol=0.32, decay=0.7)
        lead_notes[off] = p

    kick_slots = [kick if v else sil for v in kick_p]
    hat_slots = [hat if v else sil for v in hat_p]
    bass_slots = [bass_notes[v] if v is not None else sil for v in bass_p]
    lead_slots = [lead_notes[v] if v is not None else sil for v in lead_p]

    tracks = [element_track(kick_slots, "k", 0, i),
              element_track(hat_slots, "h", 0, i),
              element_track(bass_slots, "b", 0, i),
              element_track(lead_slots, "l", 0, i)]
    out = LIB / f"track_{i:02d}.mp3"
    inputs = []
    for t in tracks:
        inputs += ["-i", str(t)]
    run(["ffmpeg", "-y", *inputs, "-filter_complex",
         f"amix=inputs=4:normalize=0,aecho=0.8:0.85:60:0.2,loudnorm=I=-11:TP=-1.0,"
         f"afade=t=in:st=0:d=0.4", str(out)])
    print(f"  track_{i:02d}.mp3  (bpm {bpm})")


if __name__ == "__main__":
    # eski 3 ambient dosyayı sil (aptal müzik)
    for old in ("warm", "mystery", "dreamy"):
        f = MUS / f"{old}.mp3"
        if f.exists():
            f.unlink()
    combos = []
    roots = [110.0, 98.0, 123.47, 130.81, 87.31]   # A2, G2, B2, C3, F2 (karanlık)
    bpms = [140, 145, 150, 132, 155]
    idx = 0
    for r_i, root in enumerate(roots):
        for k in range(2):
            combos.append((idx, bpms[r_i], root,
                           KICKS[idx % len(KICKS)], HATS[idx % len(HATS)],
                           BASSLINES[idx % len(BASSLINES)], LEADS[idx % len(LEADS)]))
            idx += 1
    for c in combos:
        build_track(*c)
    for f in TMP.glob("*"):
        f.unlink()
    TMP.rmdir()
    print(f"Bitti. {idx} parçalık kütüphane -> {LIB}")
