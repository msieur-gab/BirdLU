"""Bird gestures for the consonants, and the letters on a scale (MUSICOLOGY.md, step 5).

Gab, 16 Nov: "we just need to try to make them sound like real birds ... since it's a combination of
letters, that should make a nice melody. But let's see what you come up with."

Built on version B of lab/variants.py (the whole range squeezed under 5.5 kHz, Gab's choice with C).
Vowels stay the trills they are. Each consonant keeps its own bird's timbre (overtones, and a share of
its own pitch line) but gets the gesture of its group:
  chip   t p k b d g c q   a short note with a clear attack, slurring down (a bird's "chip" call)
  buzz   s f z v j x h     a fast trill of tiny notes, 26 ms apart (a finch's buzz)
  hum    m n               a soft, round arc, smaller overtones
  flow   l                 a glide up
         w                 a glide down
         r                 a short rolled trill: three quick notes, each sliding down
Versions written:
  gesture  B + the gestures above
  scale    gesture, with every letter (vowels too) moved to the nearest note without sharps or flats
           (do ré mi fa sol la si; A4 = 440 Hz), so that any word is sung on one scale
Writes birds/variants/<version>/<letter>.wav and adds them to birds/variants/variants.json.
Run:  .venv/bin/python lab/gestures.py   (after lab/variants.py)
"""
import json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, level, CAP, OUT, ROOT
from sketch import CONSONANTS, SR
from synth import sing, trim

GROUP = {**{c: "chip" for c in "tpkbdgcq"}, **{c: "buzz" for c in "sfzvjxh"}, **{c: "hum" for c in "mn"},
         "l": "glide up", "w": "glide down", "r": "roll"}
OWN = 0.3          # share of the bird's own pitch line kept under the gesture
NATURAL = [0, 2, 4, 5, 7, 9, 11]   # do ré mi fa sol la si, in semitones from do


def gesture(m, kind):
    m = dict(m)
    own = np.array(m["shape"]); own = own - own.mean()
    u = np.linspace(0, 1, len(own))
    if kind == "chip":
        d = min(m["note_dur"], 0.06)
        env = np.minimum(1, u / 0.08) * np.exp(-3.5 * u)
        m.update(note_dur=d, period=d, shape=list(OWN * own + np.linspace(0.12, -0.14, len(u))), env=list(env / env.max()))
    elif kind == "buzz":
        m.update(notes=4, period=0.026, note_dur=0.022, pitch_drift=0.0, level_drift=-1.0, accel=0.0,
                 shape=list(0.6 * own), env=list(np.sin(np.pi * u) ** 0.7))
    elif kind == "hum":
        m.update(note_dur=0.11, period=0.11, shape=list(OWN * own + 0.08 * np.sin(np.pi * u)),
                 env=list(np.sin(np.pi * u) ** 1.5), overtones=[o * 0.5 for o in m["overtones"]])
    elif kind in ("glide up", "glide down"):
        s = np.linspace(-0.18, 0.18, len(u)) * (1 if kind == "glide up" else -1)
        d = max(m["note_dur"], 0.09)
        m.update(note_dur=d, period=d, shape=list(OWN * own + s), env=list(np.sin(np.pi * u) ** 0.8))
    elif kind == "roll":
        m.update(notes=3, period=0.032, note_dur=0.028, pitch_drift=-0.03, level_drift=-1.5, accel=0.0,
                 shape=list(OWN * own + np.linspace(0.1, -0.1, len(u))), env=list(np.sin(np.pi * u) ** 0.8))
    return m


def nearest_natural(hz):
    m = 69 + 12 * np.log2(hz / 440)
    base = 12 * np.floor(m / 12)
    cands = [base + k + o for o in (-12, 0, 12) for k in NATURAL]
    best = min(cands, key=lambda c: abs(c - m))
    return float(2 ** ((best - m) / 12)), best


def main():
    M = models()
    info = json.load(open(os.path.join(OUT, "variants.json")))
    B = info["versions"]["cap"]
    main_today = {c: s["main"] for c, s in json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"].items()}
    names = ["do", "do#", "ré", "ré#", "mi", "fa", "fa#", "sol", "sol#", "la", "la#", "si"]
    for version in ("gesture", "scale"):
        os.makedirs(os.path.join(OUT, version), exist_ok=True)
        info["versions"][version] = {}
        for ch, m in M.items():
            m = dict(m)
            f = B[ch]["main"] / main_today[ch]          # B's move down
            changed = [f"{12 * np.log2(f):+.1f} st"] if abs(12 * np.log2(f)) > 0.05 else []
            if ch in GROUP:
                m = gesture(m, GROUP[ch]); changed.append(GROUP[ch])
            main_hz = B[ch]["main"]
            if version == "scale":
                g, note = nearest_natural(main_hz)
                f *= g; main_hz *= g
                changed.append(f"{names[int(note) % 12]}{int(note) // 12 - 1}")
            m["pitch"] = m["pitch"] * f
            y = level(trim(sing(m, seed=ord(ch))))
            sf.write(os.path.join(OUT, version, f"{ch}.wav"), y, SR, subtype="PCM_16")
            info["versions"][version][ch] = dict(file=f"{version}/{ch}.wav", dur=round(len(y) / SR, 4),
                                                 main=round(main_hz), changed=", ".join(changed))
        print(version, {c: d["changed"] for c, d in info["versions"][version].items()})
    info["gestures"] = GROUP
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
