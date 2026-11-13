"""Candidate sounds for punctuation and the number sign, for Gab to choose by ear.

Each sign gets three candidates, all real bird notes from our recordings, rebuilt by the same
synthesizer as the letters, chosen for the gesture the sign should have:
  .   a falling call: the end of a phrase
  ?   a rising call: a voice rises on a question
  !   a short, bright call
  ,   a breath: a soft, low, short note
  '   a tiny tick (l'été)
  -   a tiny tick, another pitch (es-tu)
  :   a distinct short call
  @   a distinct short call
  #   the number sign: digits are sung as # then a–j (1–9, 0), as in Braille
Among the notes with the right gesture, the ones least like any letter, frame call or other sign
(on clean sound) are kept. A real test decides afterwards.

Writes birds/signs/<name>-<k>.wav and birds/signs/candidates.json.
Run:  .venv/bin/python lab/signs.py
"""
import json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, features, shape, template, match, ROOT
from choose_consonants import pool
from synth import note_model, norm
from sketch import CONSONANTS, VOWELS, cut, SR

OUT = os.path.join(ROOT, "birds", "signs")
NAMES = {".": "period", "?": "question", "!": "exclamation", ",": "comma", "'": "apostrophe", "-": "hyphen",
         ":": "colon", "@": "at", "#": "number"}


def gesture(y):
    """Pitch slope (octaves from start to end), pitch (Hz) and length (s) of a note as sung."""
    m = note_model(norm(y))
    s = np.array(m["shape"])
    k = max(1, len(s) // 6)
    return float(np.mean(s[-k:]) - np.mean(s[:k])), float(m["pitch"]), len(y) / SR


WANT = {
    ".": lambda sl, p, d: sl < -0.25,
    "?": lambda sl, p, d: sl > 0.25,
    "!": lambda sl, p, d: p > 5000 and d < 0.10,
    ",": lambda sl, p, d: p < 3200 and d < 0.10,
    "'": lambda sl, p, d: d < 0.06,
    "-": lambda sl, p, d: d < 0.07,
    ":": lambda sl, p, d: True,
    "@": lambda sl, p, d: True,
    "#": lambda sl, p, d: d > 0.06,
}


def main():
    v, snd, sr = load_voice()
    used = {("syllable", s) if isinstance(s, str) else ("cut",) + tuple(s) for s in CONSONANTS.values()}
    def is_used(spec):
        for u in used:
            if spec[0] == u[0] == "syllable" and spec[1] == u[1]:
                return True
            if spec[0] == u[0] == "cut" and spec[1] == u[1] and abs(spec[2] - u[2]) < 0.03:
                return True
        return False
    cands = [(name, spec, y) for name, spec, y in pool() if not is_used(spec)]
    print(f"{len(cands)} unused bird notes")
    fixed = [snd[c] for c in v["letters"]] + [snd["chiff"], snd["chaff"]]
    tf = [template(y, SR) for y in fixed]
    pf = [shape(features(y, SR)[0]) for y in fixed]
    info = []
    for name, spec, y in cands:
        sl, p, d = gesture(y)
        t = template(y, SR)
        P = shape(features(y, SR)[0])
        # how much it looks like the closest letter or frame call, both ways (clean sound)
        sim = max(max(match(P, tb).max(), match(pb, t).max()) for tb, pb in zip(tf, pf))
        info.append(dict(name=name, spec=spec, y=y, slope=sl, pitch=p, dur=d, sim=float(sim), t=t, P=P))
    os.makedirs(OUT, exist_ok=True)
    out, taken = {}, []
    for sign in NAMES:
        ok = [c for c in info if WANT[sign](c["slope"], c["pitch"], c["dur"]) and c["name"] not in {t["name"] for t in taken}]
        def worst(c):   # closest letter, frame or sign already chosen
            s = c["sim"]
            for t in taken:
                s = max(s, match(c["P"], t["t"]).max(), match(t["P"], c["t"]).max())
            return s
        ok.sort(key=worst)
        picks = ok[:3]
        like = [worst(c) for c in picks]
        taken += picks
        out[sign] = []
        for k, (c, lk) in enumerate(zip(picks, like), 1):
            fn = f"{NAMES[sign]}-{k}.wav"
            sf.write(os.path.join(OUT, fn), c["y"], SR, subtype="PCM_16")
            out[sign].append(dict(file=fn, source=c["name"], spec=list(c["spec"]), slope_oct=round(c["slope"], 2),
                                  pitch=round(c["pitch"]), dur=round(c["dur"], 3), likeness_to_nearest=round(float(lk), 2)))
        print(sign, " | ".join(f"{o['source']} slope {o['slope_oct']:+.2f} {o['pitch']} Hz {o['dur'] * 1000:.0f} ms like {o['likeness_to_nearest']:.2f}" for o in out[sign]))
    json.dump(dict(names=NAMES, candidates=out), open(os.path.join(OUT, "candidates.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
