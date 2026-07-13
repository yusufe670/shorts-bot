#!/usr/bin/env python3
"""
Telifsiz DRIFT PHONK beat kütüphanesi (Murder in My Mind TARZI, özgün — telif yok):
distorted 808 bas + metalik cowbell melodi + agresif hi-hat + sert kick.
assets/music/lib/track_00.mp3 ... -> generate_motorsport rastgele seçer.
Bir kez: python scripts/make_music.py
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUS = ROOT / "assets" / "music"
LIB = MUS / "lib"
TMP = MUS / "_tmp"
for d in (LIB, TMP):
    d.mkdir(parents=True, exist_ok=True)

BARS = 16
# doğal minör (phonk melodileri için)
MINOR = [0, 2, 3, 5, 7, 8, 10, 12]


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def note_hz(root, semis):
    return root * (2 ** (semis / 12.0))


def s_kick(path, step):
    # sert kick: alçak sinüs + tık, hızlı düşüş, distortion
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=52:duration={step:.3f}",
         "-af", f"volume=2.2,asoftclip=type=atan,afade=t=out:st=0:d={step*0.85:.3f},volume=1.5", str(path)])


def s_hat(path, step):
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anoisesrc=d={step:.3f}:c=pink:a=0.5",
         "-af", f"highpass=f=8000,afade=t=out:st=0:d={step*0.4:.3f},volume=0.55", str(path)])


def s_silence(path, step):
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={step:.3f}", str(path)])


def s_bass(path, hz, step):
    # distorted 808: sinüs + overdrive
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={hz:.2f}:duration={step:.3f}",
         "-af", f"volume=2.6,asoftclip=type=tanh,lowpass=f=2500,"
         f"afade=t=in:st=0:d=0.004,afade=t=out:st={step*0.9:.3f}:d={step*0.12+0.01:.3f},volume=0.6", str(path)])


def s_cowbell(path, hz, step):
    # metalik cowbell: detune'lu harmonikler + distortion (phonk lead)
    run(["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"sine=frequency={hz:.2f}:duration={step:.3f}",
         "-f", "lavfi", "-i", f"sine=frequency={hz*1.5:.2f}:duration={step:.3f}",
         "-f", "lavfi", "-i", f"sine=frequency={hz*2.01:.2f}:duration={step:.3f}",
         "-f", "lavfi", "-i", f"sine=frequency={hz*3.02:.2f}:duration={step:.3f}",
         "-filter_complex",
         f"[0][1][2][3]amix=inputs=4:normalize=0,volume=3.5,asoftclip=type=atan,"
         f"highpass=f=300,afade=t=in:st=0:d=0.002,afade=t=out:st={step*0.55:.3f}:d={step*0.45:.3f},"
         f"volume=0.34", str(path)])


def element(slots, name, i):
    lst = TMP / f"{name}_{i}.txt"
    lst.write_text("".join(f"file '{s.as_posix()}'\n" for s in slots), encoding="utf-8")
    bar = TMP / f"{name}_{i}_bar.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(bar)])
    full = TMP / f"{name}_{i}_full.wav"
    run(["ffmpeg", "-y", "-stream_loop", str(BARS - 1), "-i", str(bar), str(full)])
    return full


# 16 adım desenler (phonk: sert kick, hızlı hat, catchy cowbell riff)
KICK_P = [
    [1,0,0,0, 0,0,1,0, 0,0,0,1, 0,0,1,0],
    [1,0,0,0, 0,1,0,0, 1,0,0,0, 0,1,0,0],
]
HAT_P = [
    [1,0,1,1, 1,0,1,0, 1,0,1,1, 1,1,1,1],
    [1,1,1,0, 1,0,1,1, 1,1,1,0, 1,0,1,1],
]
BASS_P = [
    [0,None,None,None, 0,None,None,None, 5,None,None,None, 3,None,None,None],
    [0,None,None,0, None,None,None,None, 7,None,None,None, 5,None,3,None],
]
# cowbell riff (minör indexleri; None=sus). Catchy, tekrarlı.
COW_P = [
    [7,None,7,5, None,3,None,0, 3,None,5,None, 7,None,5,3],
    [0,None,3,None, 5,None,3,0, None,7,None,5, 3,None,0,None],
    [5,None,5,7, None,5,3,None, 0,None,3,5, None,3,None,0],
]


def build(i, bpm, root, kp, hp, bp, cp):
    step = 60.0 / bpm / 4.0
    kick = TMP / f"k_{i}.wav"; s_kick(kick, step)
    hat = TMP / f"h_{i}.wav"; s_hat(hat, step)
    sil = TMP / f"s_{i}.wav"; s_silence(sil, step)
    bnotes, cnotes = {}, {}
    for off in set(x for x in bp if x is not None):
        p = TMP / f"b_{i}_{off}.wav"; s_bass(p, note_hz(root / 2, MINOR[off % len(MINOR)]), step); bnotes[off] = p
    for off in set(x for x in cp if x is not None):
        p = TMP / f"c_{i}_{off}.wav"; s_cowbell(p, note_hz(root * 2, MINOR[off % len(MINOR)]), step); cnotes[off] = p

    ek = element([kick if v else sil for v in kp], "k", i)
    eh = element([hat if v else sil for v in hp], "h", i)
    eb = element([bnotes[v] if v is not None else sil for v in bp], "b", i)
    ec = element([cnotes[v] if v is not None else sil for v in cp], "c", i)

    out = LIB / f"track_{i:02d}.mp3"
    run(["ffmpeg", "-y", "-i", str(ek), "-i", str(eh), "-i", str(eb), "-i", str(ec),
         "-filter_complex",
         "amix=inputs=4:normalize=0,asoftclip=type=atan,loudnorm=I=-9:TP=-1.0,"
         "afade=t=in:st=0:d=0.3", str(out)])
    print(f"  track_{i:02d}.mp3  (phonk, {bpm}bpm)")


if __name__ == "__main__":
    for old in ("warm", "mystery", "dreamy"):
        f = MUS / f"{old}.mp3"
        if f.exists():
            f.unlink()
    for f in LIB.glob("*.mp3"):
        f.unlink()
    roots = [110.0, 98.0, 116.54, 130.81, 103.83]   # A2 G2 A#2 C3 G#2 (karanlık)
    bpms = [145, 150, 140, 155, 148]
    i = 0
    for r_i, root in enumerate(roots):
        for k in range(2):
            build(i, bpms[r_i], root,
                  KICK_P[i % len(KICK_P)], HAT_P[i % len(HAT_P)],
                  BASS_P[i % len(BASS_P)], COW_P[i % len(COW_P)])
            i += 1
    for f in TMP.glob("*"):
        f.unlink()
    TMP.rmdir()
    print(f"Bitti. {i} phonk parça -> {LIB}")
