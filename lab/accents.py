"""Candidate accent calls, for Gab to choose by ear (14 Nov).

An accented letter is sung as its plain letter, then a short accent call: à = a + grave, ñ = n + tilde,
ç = c + cedilla. If the accent call is lost, the plain letter is still there ("ecole", never a broken
word). Gab: "at least we are sure we are not losing the letter."

Each accent gets three candidates, all real bird notes from our recordings, rebuilt by the same
synthesizer as the letters, with the gesture of the mark drawn over the letter:
  ´  acute       a short rising call
  `  grave       a short falling call
  ^  circumflex  up then down
  ¨  diaeresis   two tiny ticks (the two dots)
  ~  tilde       a wavering call
  ¸  cedilla     a low short note (the hook below the letter)
Among the notes with the right gesture, the ones least like any letter, sign, frame call or accent
already chosen (on clean sound) are kept, so the six stay apart from each other. A real test decides.

Writes birds/accents/<name>-<k>.wav and birds/accents/candidates.json.
Run:  .venv/bin/python lab/accents.py
"""
import json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, features, shape, template, match, ROOT
from choose_consonants import pool
from signs import gesture
from sketch import CONSONANTS, SR

OUT = os.path.join(ROOT, "birds", "accents")
# the strictest gestures pick first
NAMES = {"^": "circumflex", "~": "tilde", "´": "acute", "`": "grave", "¸": "cedilla", "¨": "diaeresis"}
TICK_GAP = 0.03   # between the diaeresis' two ticks


def contour(y):
    from synth import note_model, norm
    return np.array(note_model(norm(y))["shape"])


def turns(s):
    """How many times the pitch line changes direction by more than 0.04 octave."""
    n, last, d = 0, s[0], 0
    for v in s[1:]:
        if d >= 0 and v < last - 0.04:
            n += d > 0; d, last = -1, v
        elif d <= 0 and v > last + 0.04:
            n += d < 0; d, last = 1, v
        elif (d >= 0 and v > last) or (d <= 0 and v < last):
            last = v
    return n


def arch(s):
    """How far the middle rises above both ends (octaves)."""
    k = max(1, len(s) // 6)
    return float(np.max(s[len(s) // 3: 2 * len(s) // 3]) - max(np.mean(s[:k]), np.mean(s[-k:])))


WANT = {
    "´": lambda c: c["slope"] > 0.18 and c["dur"] < 0.12,
    "`": lambda c: c["slope"] < -0.25 and c["dur"] < 0.10,
    "^": lambda c: c["arch"] > 0.15 and c["dur"] < 0.12,
    "¨": lambda c: c["dur"] < 0.06 and abs(c["slope"]) < 0.3,   # dots: plain ticks
    "~": lambda c: c["turns"] >= 2 and c["dur"] < 0.14,
    "¸": lambda c: c["pitch"] < 3200 and c["dur"] < 0.10,
}


def main():
    v, snd, sr = load_voice()
    used = {("syllable", s) if isinstance(s, str) else ("cut",) + tuple(s) for s in CONSONANTS.values()}
    sign_src = {d.get("source") for d in v["letters"].values() if d.get("sign")}
    def is_used(name, spec):
        if name in sign_src or "Chiffchaff" in name:   # the chiffchaff opens and closes every message
            return True
        for u in used:
            if spec[0] == u[0] == "syllable" and spec[1] == u[1]:
                return True
            if spec[0] == u[0] == "cut" and spec[1] == u[1] and abs(spec[2] - u[2]) < 0.03:
                return True
        return False
    cands = [(name, spec, y) for name, spec, y in pool() if not is_used(name, spec)]
    print(f"{len(cands)} unused bird notes")
    fixed = [snd[c] for c in v["letters"]] + [snd["chiff"], snd["chaff"]]
    tf = [template(y, SR) for y in fixed]
    pf = [shape(features(y, SR)[0]) for y in fixed]
    info = []
    for name, spec, y in cands:
        sl, p, d = gesture(y)
        s = contour(y)
        t = template(y, SR)
        P = shape(features(y, SR)[0])
        sim = max(max(match(P, tb).max(), match(pb, t).max()) for tb, pb in zip(tf, pf))
        info.append(dict(name=name, spec=spec, y=y, slope=sl, pitch=p, dur=d, turns=turns(s), arch=arch(s),
                         sim=float(sim), t=t, P=P))
    os.makedirs(OUT, exist_ok=True)
    out, taken = {}, []
    for acc in NAMES:
        ok = [c for c in info if WANT[acc](c) and c["name"] not in {t["name"] for t in taken}]
        def worst(c):   # closest letter, sign, frame or accent already chosen
            s = c["sim"]
            for t in taken:
                s = max(s, match(c["P"], t["t"]).max(), match(t["P"], c["t"]).max())
            return s
        ok.sort(key=worst)
        picks = ok[:3]
        like = [worst(c) for c in picks]
        taken += picks
        out[acc] = []
        for k, (c, lk) in enumerate(zip(picks, like), 1):
            y = c["y"]
            if acc == "¨":
                y = np.concatenate([y, np.zeros(int(TICK_GAP * SR)), y])
            fn = f"{NAMES[acc]}-{k}.wav"
            sf.write(os.path.join(OUT, fn), y, SR, subtype="PCM_16")
            out[acc].append(dict(file=fn, source=c["name"], spec=list(c["spec"]), slope_oct=round(c["slope"], 2),
                                 pitch=round(c["pitch"]), dur=round(len(y) / SR, 3), turns=c["turns"],
                                 arch_oct=round(c["arch"], 2), likeness_to_nearest=round(float(lk), 2)))
        print(acc, f"{len(ok)} fit |", " | ".join(f"{o['source']} slope {o['slope_oct']:+.2f} {o['pitch']} Hz "
                                                 f"{o['dur'] * 1000:.0f} ms like {o['likeness_to_nearest']:.2f}" for o in out[acc]))
    json.dump(dict(names=NAMES, candidates=out), open(os.path.join(OUT, "candidates.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
