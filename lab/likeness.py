"""How alike two letters look to the decoder, with a little room echo: a guide for designing letters (MUSICOLOGY.md,
step 11). It is not a test: real recordings decide (simulated rooms gave false confidence on 13 Nov).

For each pair of letters a, b: the decoder's own comparison (lab/decode.py: sound picture, shape of each 5 ms
column, template slid along) of a heard through a simple echo against b's template, and the other way round;
the larger of the two. 1.0 = identical pictures. The echo: the direct sound plus an exponentially fading noise
tail (0.6 s to fade 60 dB) at equal energy, roughly a room at 20 cm–2 m. Fixed seed.

Checked against the real tests: does it rank the pairs actually swapped in v9 (voice D) and v10 (voice F) among
the most alike?
Run:  .venv/bin/python lab/likeness.py
"""
import os, sys
import numpy as np
from scipy.signal import fftconvolve

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, features, shape, template, match, ROOT

RT60 = 0.6


def room(sr, rt60=RT60, seed=3):
    n = int(rt60 * sr)
    t = np.arange(n) / sr
    tail = np.random.default_rng(seed).normal(0, 1, n) * np.exp(-6.91 * t / rt60)
    tail *= 1 / np.sqrt(np.sum(tail ** 2))
    h = tail.copy(); h[0] += 1.0
    return h


def likeness(snd, sr, letters, h=None):
    h = room(sr) if h is None else h
    pad = np.zeros(int(0.05 * sr))
    pic, tpl = {}, {}
    for c in letters:
        y = np.concatenate([pad, snd[c], np.zeros(int(0.3 * sr))])
        heard = fftconvolve(y, h)[: len(y)]
        pic[c] = shape(features(heard, sr)[0])
        tpl[c] = template(snd[c], sr)
    L = {}
    for i, a in enumerate(letters):
        for b in letters[i + 1:]:
            L[(a, b)] = float(max(match(pic[a], tpl[b]).max(), match(pic[b], tpl[a]).max()))
    return L


def report(name, voice_dir, swapped=()):
    v, snd, sr = load_voice(voice_dir)
    letters = [c for c in v["letters"] if c.isalpha()]
    L = likeness(snd, sr, letters)
    ranked = sorted(L, key=L.get, reverse=True)
    rank = {p: k + 1 for k, p in enumerate(ranked)}
    print(f"\n{name}: most alike pairs:", ", ".join(f"{a}{b} {L[(a, b)]:.2f}" for a, b in ranked[:12]))
    for a, b in swapped:
        p = (a, b) if (a, b) in L else (b, a)
        print(f"   swapped in the room: {a}/{b}  likeness {L[p]:.2f}, rank {rank[p]} of {len(L)}")
    pen = sum(max(0, l - 0.5) ** 2 for l in L.values())
    print(f"   pairs above 0.75: {sum(l > 0.75 for l in L.values())}, above 0.65: {sum(l > 0.65 for l in L.values())}, "
          f"sum of (likeness − 0.5)² over 0.5: {pen:.2f}")
    return L


def main():
    report("approved voice (v8: 2.6 % at 30 cm)", os.path.join(ROOT, "birds", "voice"), [("r", "p"), ("r", "j")])
    report("D (v9: 6.3 % at 20 cm)", os.path.join(ROOT, "birds", "voices", "nightingale-d"),
           [("r", "j"), ("t", "h"), ("b", "z"), ("p", "q"), ("g", "q"), ("x", "v")])
    report("F (v10: 10.8 % at 20 cm)", os.path.join(ROOT, "birds", "voices", "nightingale-f"),
           [("r", "n"), ("d", "z"), ("b", "s")])
    if os.path.exists(os.path.join(ROOT, "birds", "voices", "nightingale-g")):
        report("G (note + curve, not tested yet)", os.path.join(ROOT, "birds", "voices", "nightingale-g"))


if __name__ == "__main__":
    main()
