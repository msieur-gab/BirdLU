"""The apostrophe heard three ways, to find what makes it sound synthetic (Gab, 16 Nov: "we need a less
synthetic sound for ' the apostrophe").

Today's ' is a blackbird note (XC446151 at 6.06 s) rebuilt from the simplified note model: one smooth
pitch line at 48 points and two overtones (lab/choose_consonants.py, synth_note). Here the same note is
also given:
  recording  the cleaned recording itself: reference only, to hear what the real note sounds like
             (recordings are not used in the voice: background hiss, decided 13 Nov)
  copy       the detailed rebuild: pitch and overtones measured every 1.45 ms (lab/synth.py, copy_of),
             so the note's own small movements are kept
Writes birds/signs/apostrophe-{today,recording,copy}.wav. Run:  .venv/bin/python lab/apostrophe.py
"""
import os, shutil, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sketch import cut, SR
from synth import copy_of, trim, norm
from decode import ROOT

SPEC = ("XC446151", 6.058, 6.121)
OUT = os.path.join(ROOT, "birds", "signs")


def level_like(y, ref):
    """Same peak as today's sign, so the comparison is not about loudness."""
    return y * (np.abs(ref).max() / (np.abs(y).max() + 1e-12))


def main():
    today, sr = sf.read(os.path.join(ROOT, "birds", "voice", "sign-apostrophe.wav"))
    assert sr == SR
    x, _ = cut(SPEC)
    rec = trim(norm(x))
    cp = trim(copy_of(norm(x)))
    shutil.copy(os.path.join(ROOT, "birds", "voice", "sign-apostrophe.wav"), os.path.join(OUT, "apostrophe-today.wav"))
    for name, y in (("recording", rec), ("copy", cp)):
        y = level_like(y, today)
        sf.write(os.path.join(OUT, f"apostrophe-{name}.wav"), y, SR, subtype="PCM_16")
        print(name, f"{len(y) / SR * 1000:.0f} ms")
    print("today", f"{len(today) / SR * 1000:.0f} ms")


if __name__ == "__main__":
    main()
