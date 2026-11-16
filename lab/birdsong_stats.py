"""How real birds move from note to note, measured on the recordings, against how our voices sing a sentence
(MUSICOLOGY.md, step 13).

Gab, 16 Nov: "do you want to listen to bird recordings before you continue? ... I'm not sure that you get a proper
feeling of what is a bird song to ground your changes" and "you make some research, but you are not really using
the result of this research".

Same note cutter for both (lab/synth.py: track, notes_of). For each note: length, pitch (median), how far the
pitch moves inside it (semitones, 10th to 90th percentile). Between two notes less than 0.25 s apart: the leap
(semitones) and the gap. A repeat: next note within 1 semitone and of similar length (within 30 %).
Run:  .venv/bin/python lab/birdsong_stats.py
"""
import glob, json, os, sys
import numpy as np
import soundfile as sf
from scipy.signal import medfilt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import track, notes_of, SR
from decode import load_voice, sing_js, ROOT
from real_test_v9 import PRESETS

SPECIES = {"XC461185": "wren", "XC543697": "wren", "XC489896": "chaffinch", "XC538310": "chaffinch",
           "XC446151": "blackbird", "XC533763": "blackbird", "XC170664": "chiffchaff", "XC478019": "chiffchaff",
           "XC433160": "nuthatch", "XC466459": "nuthatch", "XC541754": "song thrush", "XC503633": "song thrush",
           "XC482886": "greenfinch", "XC183761": "greenfinch", "XC531169": "yellowhammer", "XC481630": "yellowhammer",
           "XC138451": "nightingale", "XC473316": "nightingale", "XC546043": "nightingale"}
st = lambda hz: 12 * np.log2(hz / 440) + 69


def measure(x):
    t, p, A = track(x)
    p = medfilt(p, 5)
    notes = []
    for s, e in notes_of(t, p, A):
        q = st(np.maximum(p[s:e + 1], 1))
        notes.append((t[s], t[e] - t[s], float(np.median(q)), float(np.percentile(q, 90) - np.percentile(q, 10))))
    leaps, gaps, rep = [], [], []
    for (t0, d0, m0, _), (t1, d1, m1, _) in zip(notes, notes[1:]):
        g = t1 - (t0 + d0)
        if g < 0.25:
            leaps.append(abs(m1 - m0)); gaps.append(g)
            rep.append(abs(m1 - m0) < 1 and abs(d1 - d0) < 0.3 * max(d0, d1))
    return notes, np.array(leaps), np.array(gaps), np.array(rep)


def row(name, notes, leaps, gaps, rep):
    d = np.array([n[1] for n in notes]) * 1000; sp = np.array([n[3] for n in notes]); m = np.array([n[2] for n in notes])
    pc = lambda a, q: np.percentile(a, q) if len(a) else np.nan
    return dict(name=name, notes=len(notes), dur_ms=round(pc(d, 50)), span_st=round(pc(sp, 50), 1),
                range_st=round(pc(m, 90) - pc(m, 10), 1), leap_med=round(pc(leaps, 50), 1), leap_p90=round(pc(leaps, 90), 1),
                leaps_over7=round(100 * np.mean(leaps > 7)) if len(leaps) else 0, repeats=round(100 * np.mean(rep)) if len(rep) else 0,
                gap_ms=round(1000 * pc(gaps, 50)))


def main():
    rows, by = [], {}
    for f in sorted(glob.glob(os.path.join(ROOT, "lab", "sources", "wav", "*.wav"))):
        x, sr = sf.read(f)
        x = (x.mean(axis=1) if x.ndim > 1 else x)[: 60 * SR]
        r = measure(x)
        by.setdefault(SPECIES[os.path.basename(f)[:-4]], []).append(r)
    for sp, rs in by.items():
        rows.append(row(sp, sum((r[0] for r in rs), []), *(np.concatenate([r[k] for r in rs]) for k in (1, 2, 3))))
    for name in ("nightingale-d", "nightingale-g", "nightingale-h"):
        v, snd, sr = load_voice(os.path.join(ROOT, "birds", "voices", name))
        v = dict(v); v["timing"] = dict(v["timing"])
        rs = []
        for p in PRESETS:
            y = sing_js(p, v, snd)
            a = int((v["timing"]["lead"] + 2.5) * SR)          # leave the opening and closing out (roughly)
            rs.append(measure(y[a: len(y) - int(2.5 * SR)]))
        rows.append(row("our " + name.split("-")[1].upper(), sum((r[0] for r in rs), []),
                        *(np.concatenate([r[k] for r in rs]) for k in (1, 2, 3))))
    keys = ["notes", "dur_ms", "span_st", "range_st", "leap_med", "leap_p90", "leaps_over7", "repeats", "gap_ms"]
    print(f"{'':14s}" + "".join(f"{k:>12s}" for k in keys))
    for r in rows:
        print(f"{r['name']:14s}" + "".join(f"{r[k]:>12}" for k in keys))
    json.dump(rows, open(os.path.join(ROOT, "birds", "birdsong-stats.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
