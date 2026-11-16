"""Three versions of the letters, to hear against today's voice (Gab, 16 Nov: "the trill effect is the
one sounding most like a bird, and short sounds with high tune or frequencies are the ones sounding the
most synthetic and harsh"; "I need to listen the result of each option and perhaps a version combining
both ideas").

Built exactly like today's voice (lab/synth.py synth_pieces, brisk; checked: the rebuild of today's
letters matches the voice files with correlation 1.0), with one change each:
  trill  every consonant shorter than 100 ms is sung as two quick notes, like a tiny trill: the second
         note a little lower (−0.03 octave) and softer (−3 dB), 12 ms apart, each note varying a little
         as the vowel trills do. Longer consonants stay one note (they are long enough to be heard
         moving); vowels are unchanged.
  cap    every letter keeps its place in the order, but the whole range is squeezed under 5.5 kHz: the
         lowest letter stays where it is, the highest goes to 5.5 kHz, and the ones between are moved
         in proportion (in semitones). Note shapes and trill speeds are unchanged.
  both   trill and cap together.
Signs and frame calls are not changed. Writes birds/variants/<version>/<letter>.wav + variants.json.
Run:  .venv/bin/python lab/variants.py
"""
import json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sketch import VOWELS, CONSONANTS, cut, SR
from synth import model_of, note_model, brisken, sing, trim, norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "birds", "variants")
SHORT = 0.100      # consonants shorter than this become two notes
GAP = 0.012        # between the two notes
DRIFT = -0.03      # octave, second note
SOFTER = -3.0      # dB, second note
CAP = 5500.0       # Hz, top of the range in "cap"


def level(y):
    loud = np.sort(np.abs(y))[-max(1, len(y) // 5):]
    return y / (np.sqrt(np.mean(loud ** 2)) + 1e-9) * 0.25


def models():
    out = {}
    for ch, spec in {**VOWELS, **CONSONANTS}.items():
        if ch in ("é", "è"):
            continue
        x, _ = cut(spec)
        m = model_of(norm(x)) if ch in VOWELS else note_model(norm(x))
        out[ch] = brisken(m, ch in VOWELS)
    return out


def main():
    M = models()
    main_hz = {c: s["main"] for c, s in json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"].items()}
    lo = min(main_hz[c] for c in M); hi = max(main_hz[c] for c in M)
    def capped(c):     # factor that moves letter c into [lo, CAP], order kept, in proportion (log scale)
        pos = np.log(main_hz[c] / lo) / np.log(hi / lo)
        return float(lo * (CAP / lo) ** pos / main_hz[c])
    info = dict(short_s=SHORT, gap_s=GAP, drift_oct=DRIFT, softer_db=SOFTER, cap_hz=CAP, versions={})
    for version in ("trill", "cap", "both"):
        os.makedirs(os.path.join(OUT, version), exist_ok=True)
        info["versions"][version] = {}
        for ch, m in M.items():
            m = dict(m)
            changed = []
            if version in ("trill", "both") and ch in CONSONANTS and m["note_dur"] < SHORT:
                m.update(notes=2, period=m["note_dur"] + GAP, pitch_drift=DRIFT, level_drift=SOFTER)
                changed.append("2 notes")
            if version in ("cap", "both"):
                f = capped(ch)
                m["pitch"] = m["pitch"] * f
                if abs(12 * np.log2(f)) > 0.05:
                    changed.append(f"{12 * np.log2(f):+.1f} st")
            y = level(trim(sing(m, seed=ord(ch))))
            sf.write(os.path.join(OUT, version, f"{ch}.wav"), y, SR, subtype="PCM_16")
            info["versions"][version][ch] = dict(file=f"{version}/{ch}.wav", dur=round(len(y) / SR, 4),
                                                 main=round(main_hz[ch] * (capped(ch) if version != "trill" else 1)),
                                                 changed=", ".join(changed))
        print(version, {c: d["changed"] for c, d in info["versions"][version].items() if d["changed"]})
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
