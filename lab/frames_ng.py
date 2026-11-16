"""The nightingale opening and closing rebuilt by our synthesizer (MUSICOLOGY.md, step 6).

Gab's picks on nightingale.html (16 Nov): opening = phrase 1.2 (XC138451 at 13.76 s, 1.7 s: sweeps, a
buzzy high passage, then six "jug" notes), closing = phrase 1.4 (XC138451 at 21.52 s, 1.1 s: a long soft
whistle, then three arched notes each with a buzz). "Let's see how it sounds with our synthesizer."

Three versions of each, from the cleaned phrase:
  copy         the detailed rebuild: the strongest pitch line and its two overtones measured every
               1.45 ms (lab/synth.py, copy_of). Follows the bird closely; one voice at a time (the
               nightingale sometimes sings two at once).
  notes        the phrase cut into its notes (lab/synth.py, notes_of); each note modelled like a letter
               (note_model: pitch line and loudness at 48 points, overtones) and sung again with the
               synthesizer's small wobble, at its own time and loudness.
  notes-lower  notes, with every note moved down like version B of the letters (the voice's range squeezed
               under 5.5 kHz, lab/variants.py), so the frame sits with the lowered letters.
Each is cut above 9 kHz (6th-order low-pass, both directions: the fast "jug" sweeps carried overtones up to
11 kHz, the harsh high top Gab's ear objects to; the listener hears 1–9 kHz only), then level-matched like
today's frame notes. Writes birds/frames-ng/{opening,closing}-<version>.wav
and birds/frames-ng/frames.json.
Run:  .venv/bin/python lab/frames_ng.py
"""
import json, os, sys
import numpy as np
import soundfile as sf
from scipy.signal import medfilt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import track, notes_of, note_model, copy_of, sing, trim, norm, HOP
from sketch import SR
from variants import CAP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "birds", "frames-ng")
PICKS = {"opening": "XC473316-16.wav", "closing": "XC138451-4.wav"}


def soften(y):
    from scipy.signal import butter, sosfiltfilt
    return sosfiltfilt(butter(6, 9000, fs=SR, output="sos"), y)


def level(y):
    loud = np.sort(np.abs(y))[-max(1, len(y) // 5):]
    return y / (np.sqrt(np.mean(loud ** 2)) + 1e-9) * 0.25


def lower(hz, lo, hi):
    """Version B's squeeze: [lo, hi] of the voice onto [lo, CAP], in proportion on a log scale."""
    if hz <= lo:
        return 1.0
    pos = np.log(hz / lo) / np.log(hi / lo)
    return float(lo * (CAP / lo) ** pos / hz)


def by_notes(x, squeeze=None, seed=1):
    t, p, A = track(x)
    p = medfilt(p, 5)
    peak = A[0].max()
    y = np.zeros(len(x) + SR // 2)
    notes = []
    for k, (s, e) in enumerate(notes_of(t, p, A)):
        a, b = int(t[s] * SR) - 4 * HOP, int(t[e] * SR) + 4 * HOP     # t is the centre of each analysis frame
        seg = x[max(0, a): b]
        if len(seg) < int(0.015 * SR):
            continue
        m = note_model(norm(np.pad(seg, 1024)))   # silence around a short note, so the analysis window fits
        a = int(t[s] * SR) - HOP
        if squeeze:
            m["pitch"] = m["pitch"] * squeeze(m["pitch"])
        z = sing(m, seed=seed + k)
        g = A[0][s:e + 1].max() / peak
        o = max(0, a)
        y[o:o + len(z)] += g * z[: len(y) - o]
        notes.append(dict(t=round(float(t[s]), 3), dur=round(m["note_dur"], 3), pitch=m["pitch"], level=round(float(g), 2)))
    return y, notes


def main():
    os.makedirs(OUT, exist_ok=True)
    main_hz = [s["main"] for s in json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"].values()]
    lo, hi = 1444.0, max(main_hz)        # the voice's lowest letter (w) and highest sound, as in lab/variants.py
    info = {}
    for which, fn in PICKS.items():
        x, sr = sf.read(os.path.join(ROOT, "birds", "nightingale", fn))
        assert sr == SR
        x = norm(x)
        versions = {
            "copy": (trim(copy_of(x)), None),
            "notes": by_notes(x),
            "notes-lower": by_notes(x, squeeze=lambda hz: lower(hz, lo, hi)),
        }
        info[which] = dict(source=fn, versions={})
        for v, (y, notes) in versions.items():
            y = level(trim(soften(y)))
            name = f"{which}-{v}.wav"
            sf.write(os.path.join(OUT, name), y, SR, subtype="PCM_16")
            info[which]["versions"][v] = dict(file=name, dur=round(len(y) / SR, 3), notes=len(notes) if notes else None)
            print(which, v, f"{len(y) / SR:.2f} s", f"{len(notes)} notes" if notes else "")
    json.dump(info, open(os.path.join(OUT, "frames.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
