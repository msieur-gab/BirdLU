"""Version K: every consonant its own place in pitch, then a bird trill on it (MUSICOLOGY.md, step 14).

Gab, 16 Nov: "why we are not putting these letters that should not be recognized as similar further away from the
Hertzian range, so to make sure that they are never in the same range. Then add like envelope around, like trill,
bell shape or curve shape or down or up ... And then we do that for every letters ... it should be straightforward."
On the sweeps page he heard "down" and "bow" as bird-like (and D).

1. Places. Two lanes of 10 places each, from E6 to about E8 (1319–5300 Hz, inside D's range):
     down lane  E6 + 0, 2.5, 5, ... 22.5 semitones
     bow lane   the same, 1.25 semitones higher
   Every consonant has a place of its own: two letters with the same shape are at least 2.5 semitones apart, and
   letters that were ever confused (real tests v9, v10, v11 and Gab's ear) at least 5 semitones apart.
2. Envelope. Each consonant is a fast trill of four short notes (26 ms, every 33 ms) of its own bird note (its
   overtones, a little of its own pitch line), each note sweeping down, or down then up (bow), 0.15 octave each side.
3. Vowels, # and @ exactly as in D.
Which letter goes where: swaps of places, lowest cost wins: how alike letters look to the decoder through a 1.0 s
echo (lab/likeness.py), weighted by how often they are used, plus a little of the step-3 rule (most used
neighbours apart). 30 seeded random starts.

Writes birds/variants/trills/<letter>.wav, version "trills" in birds/variants/variants.json, birds/trill-voice.json.
Run:  .venv/bin/python lab/trill_voice.py
"""
import json, os, sys, time
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, level, OUT, ROOT
from gestures import GROUP
from synth import sing, trim
from sketch import SR
from decode import match, load_voice
from likeness import room
from curves import picture, note_name

A = 0.15
U = np.linspace(0, 1, 48)
SHAPE = {"down": np.linspace(A, -A, 48), "bow": A - 2 * A * np.sin(np.pi * U)}
BASE = 88.0                                   # E6
PLACES = [("down", BASE + 2.5 * i) for i in range(10)] + [("bow", BASE + 1.25 + 2.5 * i) for i in range(10)]
CONFUSED = [("r", "j"), ("t", "h"), ("b", "z"), ("p", "q"), ("g", "q"), ("x", "v"),          # v9 and Gab's ear
            ("r", "n"), ("d", "z"), ("b", "s"),                                              # v10
            ("t", "p"), ("d", "q"), ("s", "d"), ("q", "h"), ("c", "f"), ("r", "l")]          # v11 far
FAR = 5.0
STARTS = 30


def trill(m, midi, kind, seed):
    m = dict(m); own = np.array(m["shape"]); own = own - own.mean()
    m.update(notes=4, period=0.033, note_dur=0.026, shape=list(SHAPE[kind] + 0.1 * own),
             env=list(np.sin(np.pi * U) ** 0.6), pitch=440 * 2 ** ((midi - 69) / 12),
             pitch_drift=0.0, level_drift=-1.0, accel=0.0)
    return level(trim(sing(m, seed=seed)))


def main():
    t0 = time.time()
    h = room(SR, 1.0)
    M = models()
    cons = sorted(GROUP)
    assert len(cons) == len(PLACES)
    v, snd, _ = load_voice(os.path.join(ROOT, "birds", "voices", "nightingale-d"))
    fixed = list("aeiouy") + ["#", "@"]
    pc = {(c, k): picture(trill(M[c], PLACES[k][1], PLACES[k][0], ord(c)), h) for c in cons for k in range(len(PLACES))}
    pf = {f: picture(snd[f], h) for f in fixed}
    like = lambda X, Y: max(match(X[0], Y[1]).max(), match(Y[0], X[1]).max())
    LF = {(c, k, f): like(pc[(c, k)], pf[f]) for c in cons for k in range(len(PLACES)) for f in fixed}
    LC = {}
    for (a, ka), Pa in pc.items():
        for (b, kb), Pb in pc.items():
            if a < b and ka != kb and abs(PLACES[ka][1] - PLACES[kb][1]) <= 8:
                LC[(a, ka, b, kb)] = like(Pa, Pb)
    print(f"likeness tables in {time.time() - t0:.0f} s", flush=True)

    B = json.load(open(os.path.join(ROOT, "birds", "bigrams.json")))
    fr = lambda x: B["letters"].get(x, 0.002)
    share = {}
    for p in B["pairs"]:
        a, b = p["pair"]
        if a != b:
            share[(a, b)] = share.get((a, b), 0) + p["mean"]; share[(b, a)] = share.get((b, a), 0) + p["mean"]
    Dv = json.load(open(os.path.join(OUT, "variants.json")))["versions"]["gesture"]
    vow = {c: 69 + 12 * np.log2(Dv[c]["main"] / 440) for c in "aeiouy"}
    pen = lambda L: 100 * max(0.0, L - 0.5) ** 2
    conf = {tuple(sorted(p)) for p in CONFUSED}

    def cost(at):                 # at: consonant -> place index
        tot = 0.0
        for i, a in enumerate(cons):
            ka, na = at[a], PLACES[at[a]][1]
            tot += sum((fr(a) + fr(f)) * pen(LF[(a, ka, f)]) for f in fixed)
            for vv in "aeiouy":
                tot += 0.1 * share.get((a, vv), 0) * max(0, 6 - abs(na - vow[vv])) / 6
            for b in cons[i + 1:]:
                kb, nb = at[b], PLACES[at[b]][1]
                tot += (fr(a) + fr(b)) * pen(LC.get((a, ka, b, kb), 0.0))
                tot += 0.1 * share.get((a, b), 0) * max(0, 6 - abs(na - nb)) / 6
                if (a, b) in conf and abs(na - nb) < FAR:
                    tot += 10
        return tot

    rng = np.random.default_rng(15)
    best = None
    for st in range(STARTS):
        at = dict(zip(cons, (int(k) for k in rng.permutation(len(PLACES)))))
        cur = cost(at)
        improved = True
        while improved:
            improved = False
            for i, a in enumerate(cons):
                for b in cons[i + 1:]:
                    at[a], at[b] = at[b], at[a]
                    c2 = cost(at)
                    if c2 < cur - 1e-9:
                        cur, improved = c2, True
                    else:
                        at[a], at[b] = at[b], at[a]
        if best is None or cur < best[0]:
            best = (cur, dict(at))
    cur, at = best
    print(f"best cost {cur:.3f} ({time.time() - t0:.0f} s)")

    info = json.load(open(os.path.join(OUT, "variants.json")))
    os.makedirs(os.path.join(OUT, "trills"), exist_ok=True)
    info["versions"]["trills"] = {}
    for ch in M:
        if ch in GROUP:
            kind, midi = PLACES[at[ch]]
            y = trill(M[ch], midi, kind, ord(ch))
            changed, main_hz = f"{kind} trill, {note_name(int(round(midi)))}", round(440 * 2 ** ((midi - 69) / 12))
        else:
            y = sf.read(os.path.join(OUT, Dv[ch]["file"]))[0]
            changed, main_hz = "as D", Dv[ch]["main"]
        sf.write(os.path.join(OUT, "trills", f"{ch}.wav"), y, SR, subtype="PCM_16")
        info["versions"]["trills"][ch] = dict(file=f"trills/{ch}.wav", dur=round(len(y) / SR, 4), main=main_hz, changed=changed)
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)
    out = {c: dict(shape=PLACES[at[c]][0], hz=round(440 * 2 ** ((PLACES[at[c]][1] - 69) / 12))) for c in cons}
    json.dump(dict(cost=round(cur, 3), consonants=out), open(os.path.join(ROOT, "birds", "trill-voice.json"), "w"), indent=1)
    for c in sorted(cons, key=lambda c: PLACES[at[c]][1]):
        print(f"  {c}  {out[c]['hz']:5d} Hz  {out[c]['shape']}")
    for a, b in CONFUSED:
        print(f"  {a}/{b}: {abs(PLACES[at[a]][1] - PLACES[at[b]][1]):.2f} st apart")


if __name__ == "__main__":
    main()
