#!/usr/bin/env python3
"""
Telifsiz, enerjik fon müziği üretir (arpej + pad + bas), yüksek/net ses seviyesiyle.
assets/music/{warm,mystery,dreamy}.mp3 dosyalarını yeniden yazar.
Bir kez çalıştırılır: python scripts/make_music.py
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUS = ROOT / "assets" / "music"
MUS.mkdir(parents=True, exist_ok=True)
TMP = MUS / "_tmp"
TMP.mkdir(exist_ok=True)

STEP = 0.24          # arpej nota süresi (sn)
TARGET = 60          # tam süre

MOODS = {
    # arpej desen (Hz)                 pad akoru (Hz)                 bas (Hz)
    "warm":    ([261.63, 329.63, 392.00, 523.25, 392.00, 329.63], [130.81, 196.00, 261.63], 65.41),
    "mystery": ([220.00, 261.63, 329.63, 440.00, 329.63, 261.63], [110.00, 164.81, 220.00], 55.00),
    "dreamy":  ([293.66, 440.00, 587.33, 440.00, 329.63, 440.00], [146.83, 220.00, 293.66], 73.42),
}


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make(mood, arp, pad, bass):
    # 1) arpej notaları -> tek desen
    notes = []
    for i, f in enumerate(arp):
        n = TMP / f"{mood}_n{i}.wav"
        run(["ffmpeg", "-y", "-f", "lavfi", "-i",
             f"sine=frequency={f}:duration={STEP}",
             "-af", f"afade=t=in:st=0:d=0.01,afade=t=out:st={STEP-0.06:.3f}:d=0.06,volume=0.5",
             str(n)])
        notes.append(n)
    lst = TMP / f"{mood}_list.txt"
    lst.write_text("".join(f"file '{n.as_posix()}'\n" for n in notes), encoding="utf-8")
    pattern = TMP / f"{mood}_pat.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(pattern)])
    # döngüyle 60 sn arpej
    arp_full = TMP / f"{mood}_arp.wav"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(pattern), "-t", str(TARGET), str(arp_full)])

    # 2) pad (sürekli akor) + bas
    pad_inputs = []
    for f in pad:
        pad_inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration={TARGET}"]
    pad_inputs += ["-f", "lavfi", "-i", f"sine=frequency={bass}:duration={TARGET}"]
    npad = len(pad) + 1
    pad_full = TMP / f"{mood}_pad.wav"
    run(["ffmpeg", "-y", *pad_inputs, "-filter_complex",
         f"amix=inputs={npad}:normalize=1,tremolo=f=0.3:d=0.4,lowpass=f=600,volume=1.4",
         str(pad_full)])

    # 3) arpej + pad karışımı -> yüksek/net (loudnorm)
    out = MUS / f"{mood}.mp3"
    run(["ffmpeg", "-y", "-i", str(arp_full), "-i", str(pad_full), "-filter_complex",
         "[0:a]volume=0.9[a];[1:a]volume=0.7[p];[a][p]amix=inputs=2:normalize=0,"
         "aecho=0.8:0.85:60:0.25,loudnorm=I=-13:TP=-1.0,"
         f"afade=t=in:st=0:d=0.8,afade=t=out:st={TARGET-3}:d=3",
         "-c:a", "libmp3lame", "-q:a", "4", str(out)])
    print(f"  {mood}.mp3 üretildi")


if __name__ == "__main__":
    for mood, (arp, pad, bass) in MOODS.items():
        make(mood, arp, pad, bass)
    # temizle
    for f in TMP.glob("*"):
        f.unlink()
    TMP.rmdir()
    print("Bitti.")
