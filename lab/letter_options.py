"""Letter by letter: options for the letters to fix, made straight with the synthesizer (MUSICOLOGY.md, step 15).

Gab, 16 Nov: "we can go letter by letter and trying to find which one needs to be solved. And perhaps we need to
add specific envelopes for letters which should be told apart" and "you go straight with the synthesizer, then I
know what I'm testing and checking is what I will get".
Letters: w ("extremely bad") and the pairs confused by the phone or by ear (r/j, t/h, b/z, p/q, g/q, x/v).
Each letter, from version D (lab/gestures.py: its own bird note model, overtones, gesture, D's pitch):
  D        as today
  x2, x3   D's sound repeated 2 or 3 times, 12 ms apart (as the vowels' trills repeat)
  sweep    one steep down-sweep, one octave in 35 ms (a "tsip", as the chaffinch's notes)
  long     one down-sweep, one octave in 80 ms (as the wren's)
  sweep x3 the steep sweep three times, 15 ms apart (as the chaffinch repeats a syllable)
A sweep runs from half an octave above D's pitch to half an octave below, moved down if it would start above
7 kHz. Writes birds/variants/letters2/<letter>-<option>.wav and options.json.
Run:  .venv/bin/python lab/letter_options.py
"""
import json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, level, OUT, ROOT
from gestures import GROUP, gesture
from synth import sing, trim
from sketch import SR

LETTERS = list("wrjthbzpqgxv")
U = np.linspace(0, 1, 48)


def d_model(M, Dv, score, c):
    m = gesture(dict(M[c]), GROUP[c]); m["pitch"] = m["pitch"] * Dv[c]["main"] / score[c]["main"]; return m


def repeat(y, k, gap):
    z = np.zeros(int(gap * SR))
    return np.concatenate(sum(([y * 10 ** (-1.0 * i / 20), z] for i in range(k)), [])[:-1])


def sweep(M, Dv, c, dur, seed):
    m = dict(M[c]); own = np.array(m["shape"]); own = own - own.mean()
    top = min(Dv[c]["main"] * 2 ** 0.5, 7000.0)
    centre = top / 2 ** 0.5
    m.update(notes=1, period=dur, note_dur=dur, shape=list(np.linspace(0.5, -0.5, 48) + 0.05 * own),
             env=list(np.minimum(1, U / 0.1) * np.exp(-1.5 * U)), pitch=centre, pitch_drift=0.0, level_drift=0.0, accel=0.0)
    return trim(sing(m, seed=seed))


def main():
    M = models()
    info = json.load(open(os.path.join(OUT, "variants.json")))
    Dv = info["versions"]["gesture"]
    score = json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"]
    out = os.path.join(OUT, "letters2"); os.makedirs(out, exist_ok=True)
    meta = {}
    for c in LETTERS:
        d = trim(sing(d_model(M, Dv, score, c), seed=ord(c)))
        s = sweep(M, Dv, c, 0.035, ord(c))
        opts = {"D": d, "x2": repeat(d, 2, 0.012), "x3": repeat(d, 3, 0.012), "sweep": s,
                "long": sweep(M, Dv, c, 0.080, ord(c)), "sweep-x3": repeat(s, 3, 0.015)}
        for k, y in opts.items():
            sf.write(os.path.join(out, f"{c}-{k}.wav"), level(y), SR, subtype="PCM_16")
        meta[c] = dict(gesture=GROUP[c], hz=Dv[c]["main"], ms={k: round(len(y) / SR * 1000) for k, y in opts.items()})
    json.dump(meta, open(os.path.join(out, "options.json"), "w"), indent=1)
    for c, m in meta.items():
        print(c, m["gesture"], m["hz"], m["ms"])


if __name__ == "__main__":
    main()
