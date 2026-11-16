"""Every sound of the voice placed on a musical staff (Gab, 16 Nov: "place all our letters and numbers on a
partition, to see how they spread").

For each letter, sign and frame call: its pitch line (the strongest ridge, as the synthesizer measures it)
and loudness over time, plus its main pitch, lowest and highest pitch, as Hz and as note names (A4 = 440 Hz).
Measures the voice only; changes nothing.

Writes birds/score.json, read by score.html.
Run:  .venv/bin/python lab/score.py
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, ROOT
from synth import track, HOP

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note(hz):
    m = 69 + 12 * np.log2(hz / 440)
    k = int(round(m))
    return f"{NAMES[k % 12]}{k // 12 - 1}", round(float(100 * (m - k)))   # name, cents off


def main():
    v, snd, sr = load_voice()
    assert sr == 44100, sr
    out = {}
    items = list(v["letters"].items()) + [(k, dict(d, frame=True)) for k, d in v["frames"].items()]
    for ch, d in items:
        x = snd[ch]
        t, p, A = track(x)
        db = 20 * np.log10(A[0] + 1e-12)
        db -= db.max()
        on = db > -30                       # the sounding part
        w = 10 ** (db[on] / 20)
        lp = np.log2(p[on])
        main_hz = float(2 ** np.average(lp, weights=w))
        lo, hi = (float(2 ** np.percentile(lp, q)) for q in (5, 95))
        step = 3                            # one point every ~4.4 ms
        pts = [[round(float(t[i] - t[0]), 4), round(float(p[i])), round(float(db[i]), 1)]
               for i in range(0, len(t), step) if on[i]]
        kind = "frame" if d.get("frame") else "sign" if d.get("sign") else "vowel" if d.get("vowel") else "consonant"
        out[ch] = dict(kind=kind, dur=round(len(x) / sr, 4), main=round(main_hz), main_note=note(main_hz)[0],
                       cents=note(main_hz)[1], low=round(lo), high=round(hi), low_note=note(lo)[0], high_note=note(hi)[0],
                       source=d.get("source", ""), points=pts)
        print(f"{ch:>6} {kind:9} {main_hz:6.0f} Hz {note(main_hz)[0]:>4}  range {note(lo)[0]}–{note(hi)[0]}")
    json.dump(dict(hop_s=HOP / sr, sounds=out), open(os.path.join(ROOT, "birds", "score.json"), "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
