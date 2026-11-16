"""Version G: note + curve for every consonant (MUSICOLOGY.md, step 11).

Gab, 16 Nov: "pitch will not be enough. It should be pitch plus the envelope of the sound" → "go ahead with
note + curve". His curves (15 Nov thinking, on the score): "the trill is like a wave ... an arc going down, arc
going up. A line going up, a line going down".

Each consonant keeps the texture of its group in version D (the sound Gab liked: "it starts to sound really like
a bird"): chip (short, sharp attack), buzz (four quick pulses), hum (soft and round, smaller overtones),
glide (l, w), roll (r, three pulses), its own bird's overtones and a little (15 %) of its own pitch line.
On top it gets
  a note   a semitone from G6 to D8 (1568–4699 Hz; with the curve it stays within about 1.3–5.9 kHz), and
  a curve  rise, fall, arc (up then down), valley (down then up), flat, or warble (a wave), each spanning
           half an octave.
Vowels (the trills of version D), # and @ do not change.

Chosen by the decoder's own eyes: lab/likeness.py measures how alike two letters look to the decoder through a
simple room echo; on the real tests it ranked the pairs actually swapped among the 8 most alike of 325 (v9, v10).
Cost, lowest wins:
  sum over letter pairs (at least one consonant) of (frequency of x + frequency of y) × 100 × max(0, likeness − 0.5)²
  + 0.1 × the step-3 cost (most used neighbours less than half an octave apart)
Search: every consonant tries every note and curve, keeping what lowers the cost, until nothing does; 12 seeded
random starts; the best is kept.

Writes birds/variants/curves/<letter>.wav, version "curves" in birds/variants/variants.json, birds/curves.json.
Run:  .venv/bin/python lab/curves.py   (after lab/gestures.py; takes a few minutes)
"""
import json, os, sys, time
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, level, OUT, ROOT
from gestures import GROUP
from synth import sing, trim
from sketch import SR
from decode import features, shape, template, match, load_voice
from likeness import room

A = 0.25                     # octaves from the centre to each end of a curve
NOTES = list(range(91, 111))  # G6 .. D8 (MIDI)
OWN = 0.15
U = np.linspace(0, 1, 48)
CURVES = {
    "rise": np.linspace(-A, A, 48),
    "fall": np.linspace(A, -A, 48),
    "arc": -A + 2 * A * np.sin(np.pi * U),
    "valley": A - 2 * A * np.sin(np.pi * U),
    "flat": np.zeros(48),
    "warble": 0.5 * A * np.sin(2 * np.pi * 2.5 * U),
}
FAR = 10                      # semitones: notes further apart than this are taken as not alike at all
STARTS = 12
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
note_name = lambda m: f"{NAMES[m % 12]}{m // 12 - 1}"


def texture(m, group):
    """Envelope, length and overtones of the group's sound in version D (lab/gestures.py), as one note."""
    m = dict(m)
    pulses = lambda k, p: np.abs(np.sin(np.pi * k * U)) ** p * np.sin(np.pi * U) ** 0.4
    if group == "chip":
        d, env = 0.07, np.minimum(1, U / 0.08) * np.exp(-3.0 * U)
    elif group == "buzz":
        d, env = 0.10, pulses(4, 0.7)
    elif group == "roll":
        d, env = 0.096, pulses(3, 0.8)
    elif group == "hum":
        d, env = 0.11, np.sin(np.pi * U) ** 1.5
        m["overtones"] = [o * 0.5 for o in m["overtones"]]
    else:   # glide up / glide down
        d, env = 0.09, np.sin(np.pi * U) ** 0.8
    m.update(notes=1, period=d, note_dur=d, env=list(env / env.max()), pitch_drift=0.0, level_drift=0.0, accel=0.0)
    return m


def build(m, group, curve, note, seed):
    own = np.array(m["shape"]); own = own - own.mean()
    m = texture(m, group)
    m["shape"] = list(CURVES[curve] + OWN * own)
    m["pitch"] = 440 * 2 ** ((note - 69) / 12)
    return level(trim(sing(m, seed=seed)))


def picture(y, h):
    pad = np.zeros(int(0.05 * SR))
    heard = fftconvolve(np.concatenate([pad, y, np.zeros(int(0.3 * SR))]), h)[: len(y) + int(0.35 * SR)]
    return shape(features(heard, SR)[0]), template(y, SR)


def main():
    t0 = time.time()
    h = room(SR)
    M = models()
    cons = sorted(GROUP)
    grp = {c: ("glide" if GROUP[c].startswith("glide") else GROUP[c]) for c in cons}
    # fixed: the vowels of D, the number call and @
    vd, snd_d, _ = load_voice(os.path.join(ROOT, "birds", "voices", "nightingale-d"))
    fixed = list("aeiouy") + ["#", "@"]
    # every candidate: consonant × curve × note
    cand, pics, tpls = [], [], []
    for c in cons:
        for k in CURVES:
            for n in NOTES:
                y = build(M[c], grp[c], k, n, seed=ord(c))
                P, T = picture(y, h)
                cand.append((c, k, n)); pics.append(P); tpls.append(T)
    fpics, ftpls = zip(*[picture(snd_d[f], h) for f in fixed])
    print(f"{len(cand)} candidates in {time.time() - t0:.0f} s", flush=True)
    N = len(cand)
    like = lambda P1, T1, P2, T2: max(match(P1, T2).max(), match(P2, T1).max())
    # candidate × fixed letters
    LF = np.array([[like(pics[i], tpls[i], fpics[j], ftpls[j]) for j in range(len(fixed))] for i in range(N)], dtype=np.float32)
    # candidate × candidate (different consonants, notes within FAR)
    LC = np.zeros((N, N), dtype=np.float32)
    for i in range(N):
        ci, _, ni = cand[i]
        for j in range(i + 1, N):
            cj, _, nj = cand[j]
            if ci != cj and abs(ni - nj) <= FAR:
                LC[i, j] = LC[j, i] = like(pics[i], tpls[i], pics[j], tpls[j])
    print(f"likeness table in {time.time() - t0:.0f} s", flush=True)

    B = json.load(open(os.path.join(ROOT, "birds", "bigrams.json")))
    freq = B["letters"]
    fr = lambda x: freq.get(x, 0.002)          # # and @ are rare
    share = {}
    for p in B["pairs"]:
        a, b = p["pair"]
        if a != b:
            share[(a, b)] = share.get((a, b), 0) + p["mean"]; share[(b, a)] = share.get((b, a), 0) + p["mean"]
    vow_note = {c: 69 + 12 * np.log2(json.load(open(os.path.join(OUT, "variants.json")))["versions"]["gesture"][c]["main"] / 440)
                for c in "aeiouy"}
    options = {c: [i for i, (cc, _, _) in enumerate(cand) if cc == c] for c in cons}
    pen = lambda L: 100 * np.maximum(0, L - 0.5) ** 2

    def cost(sel):            # sel: consonant -> candidate index
        total = 0.0
        idx = [sel[c] for c in cons]
        for a_i, a in enumerate(cons):
            i = sel[a]
            total += sum((fr(a) + fr(f)) * pen(LF[i, j]) for j, f in enumerate(fixed))
            for b in cons[a_i + 1:]:
                j = sel[b]
                total += (fr(a) + fr(b)) * pen(LC[i, j])
                total += 0.1 * share.get((a, b), 0) * max(0, 6 - abs(cand[i][2] - cand[j][2])) / 6
            for v in "aeiouy":
                total += 0.1 * share.get((a, v), 0) * max(0, 6 - abs(cand[i][2] - vow_note[v])) / 6
        return float(total)

    rng = np.random.default_rng(11)
    best = None
    for s in range(STARTS):
        sel = {c: int(rng.choice(options[c])) for c in cons}
        cur = cost(sel)
        improved = True
        while improved:
            improved = False
            for c in rng.permutation(cons):
                keep = sel[c]
                for o in options[c]:
                    sel[c] = o
                    c2 = cost(sel)
                    if c2 < cur - 1e-9:
                        cur, keep, improved = c2, o, True
                sel[c] = keep
        print(f"start {s + 1}: cost {cur:.3f}", flush=True)
        if best is None or cur < best[0]:
            best = (cur, dict(sel))
    cur, sel = best

    # build the voice
    info = json.load(open(os.path.join(OUT, "variants.json")))
    os.makedirs(os.path.join(OUT, "curves"), exist_ok=True)
    info["versions"]["curves"] = {}
    D = info["versions"]["gesture"]
    for ch in M:
        if ch in GROUP:
            c, k, n = cand[sel[ch]]
            y = build(M[ch], grp[ch], k, n, seed=ord(ch))
            changed = f"{GROUP[ch]}, {k}, {note_name(n)}"
            main_hz = round(440 * 2 ** ((n - 69) / 12))
        else:
            y = sf.read(os.path.join(OUT, D[ch]["file"]))[0]
            changed, main_hz = "as D", D[ch]["main"]
        sf.write(os.path.join(OUT, "curves", f"{ch}.wav"), y, SR, subtype="PCM_16")
        info["versions"]["curves"][ch] = dict(file=f"curves/{ch}.wav", dur=round(len(y) / SR, 4), main=main_hz, changed=changed)
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)
    out = {c: dict(group=GROUP[c], curve=cand[sel[c]][1], note=note_name(cand[sel[c]][2])) for c in cons}
    json.dump(dict(cost=round(cur, 3), consonants=out), open(os.path.join(ROOT, "birds", "curves.json"), "w"), ensure_ascii=False, indent=1)
    for c in sorted(cons, key=lambda c: cand[sel[c]][2]):
        print(f"  {c}  {out[c]['note']:4s} {out[c]['curve']:7s} ({GROUP[c]})")
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
