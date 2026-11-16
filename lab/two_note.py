"""Version L: every consonant two short bird notes, from 7 pitch levels far apart (MUSICOLOGY.md, step 14).

Gab, 16 Nov: "why we are not putting these letters that should not be recognized as similar further away from the
Hertzian range, so to make sure that they are never in the same range. Then add like envelope around ... down ...
And then we do that for every letters ... it should be straightforward."

Why two notes: 20 consonants in two octaves leave about one semitone each (version K: neighbours 1.25 semitones
apart, read wrong even on clean sound). Seven levels a major third (4 semitones) apart, E6 G#6 C7 E7 G#7 C8 E8
(1319–5274 Hz), and a letter = an ordered pair of levels (like DTMF phone tones, or the chiffchaff's two notes):
every note is 4 semitones from any other level. A letter's leap is 4 or 8 semitones (birds: median 2–4, often
more; lab/birdsong_stats.py).
Each note: 34 ms of the letter's own bird note (its overtones and a little of its own pitch line), a slight down
sweep (Gab: "mostly the down is working"), 10 ms apart; the second note 1.5 dB softer.
Vowels, # and @ exactly as in D.
Which letter gets which pair: swaps, lowest cost wins: how alike letters look to the decoder through a 1.0 s echo
(lab/likeness.py), weighted by how often they are used; letters ever confused (real tests, Gab's ear) share no
note at the same position; the most used letters get the smaller leaps.

Writes birds/variants/twonote/<letter>.wav, version "twonote" in birds/variants/variants.json, birds/two-note.json.
Run:  .venv/bin/python lab/two_note.py
"""
import itertools, json, os, sys, time
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
from trill_voice import CONFUSED

LEVELS = [88 + 4 * i for i in range(7)]            # E6 .. E8
PAIRS = [(i, j) for i in range(7) for j in range(7) if 1 <= abs(i - j) <= 2]   # 22 ordered pairs
NOTE, GAP, SWEEP = 0.034, 0.010, 0.07
U = np.linspace(0, 1, 48)
STARTS = 30


def two_notes(m, pair, seed):
    m = dict(m); own = np.array(m["shape"]); own = own - own.mean()
    out = []
    for k, lv in enumerate(pair):
        n = dict(m)
        n.update(notes=1, period=NOTE, note_dur=NOTE, shape=list(np.linspace(SWEEP, -SWEEP, 48) + 0.1 * own),
                 env=list(np.minimum(1, U / 0.15) * np.sin(np.pi * U) ** 0.5), pitch=440 * 2 ** ((LEVELS[lv] - 69) / 12),
                 pitch_drift=0.0, level_drift=0.0, accel=0.0)
        y = trim(sing(n, seed=seed + k)) * 10 ** (-1.5 * k / 20)
        out += [y, np.zeros(int(GAP * SR))]
    return level(np.concatenate(out[:-1]))


def main():
    t0 = time.time()
    h = room(SR, 1.0)
    M = models()
    cons = sorted(GROUP)
    v, snd, _ = load_voice(os.path.join(ROOT, "birds", "voices", "nightingale-d"))
    fixed = list("aeiouy") + ["#", "@"]
    pc = {(c, p): picture(two_notes(M[c], PAIRS[p], ord(c)), h) for c in cons for p in range(len(PAIRS))}
    pf = {f: picture(snd[f], h) for f in fixed}
    like = lambda X, Y: max(match(X[0], Y[1]).max(), match(Y[0], X[1]).max())
    LF = {(c, p, f): like(pc[(c, p)], pf[f]) for (c, p) in pc for f in fixed}
    LC = {(a, pa, b, pb): like(pc[(a, pa)], pc[(b, pb)]) for (a, pa) in pc for (b, pb) in pc if a < b and pa != pb}
    print(f"likeness tables in {time.time() - t0:.0f} s", flush=True)

    B = json.load(open(os.path.join(ROOT, "birds", "bigrams.json")))
    fr = lambda x: B["letters"].get(x, 0.002)
    pen = lambda L: 100 * max(0.0, L - 0.5) ** 2
    conf = {tuple(sorted(p)) for p in CONFUSED}

    def cost(at):                # consonant -> pair index (distinct)
        tot = 0.0
        for i, a in enumerate(cons):
            pa = at[a]
            tot += sum((fr(a) + fr(f)) * pen(LF[(a, pa, f)]) for f in fixed)
            tot += 0.5 * fr(a) * (abs(PAIRS[pa][0] - PAIRS[pa][1]) - 1)      # small leaps for used letters
            for b in cons[i + 1:]:
                pb = at[b]
                tot += (fr(a) + fr(b)) * pen(LC[(a, pa, b, pb)])
                if (a, b) in conf and (PAIRS[pa][0] == PAIRS[pb][0] or PAIRS[pa][1] == PAIRS[pb][1]):
                    tot += 10
        return tot

    rng = np.random.default_rng(16)
    best = None
    for st in range(STARTS):
        perm = [int(k) for k in rng.permutation(len(PAIRS))]
        at, spare = dict(zip(cons, perm)), perm[len(cons):]
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
                for k, s in enumerate(spare):
                    old = at[a]; at[a] = s
                    c2 = cost(at)
                    if c2 < cur - 1e-9:
                        cur, improved = c2, True; spare[k] = old
                    else:
                        at[a] = old
        if best is None or cur < best[0]:
            best = (cur, dict(at))
    cur, at = best
    print(f"best cost {cur:.3f} ({time.time() - t0:.0f} s)")

    info = json.load(open(os.path.join(OUT, "variants.json")))
    Dv = info["versions"]["gesture"]
    os.makedirs(os.path.join(OUT, "twonote"), exist_ok=True)
    info["versions"]["twonote"] = {}
    nm = lambda p: "–".join(note_name(LEVELS[k]) for k in PAIRS[p])
    for ch in M:
        if ch in GROUP:
            y = two_notes(M[ch], PAIRS[at[ch]], ord(ch))
            changed, main_hz = f"two notes {nm(at[ch])}", round(440 * 2 ** ((LEVELS[PAIRS[at[ch]][0]] - 69) / 12))
        else:
            y = sf.read(os.path.join(OUT, Dv[ch]["file"]))[0]
            changed, main_hz = "as D", Dv[ch]["main"]
        sf.write(os.path.join(OUT, "twonote", f"{ch}.wav"), y, SR, subtype="PCM_16")
        info["versions"]["twonote"][ch] = dict(file=f"twonote/{ch}.wav", dur=round(len(y) / SR, 4), main=main_hz, changed=changed)
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(dict(cost=round(cur, 3), levels=[note_name(l) for l in LEVELS], consonants={c: nm(at[c]) for c in cons}),
              open(os.path.join(ROOT, "birds", "two-note.json"), "w"), ensure_ascii=False, indent=1)
    for c in sorted(cons, key=lambda c: PAIRS[at[c]]):
        print(f"  {c}  {nm(at[c])}")


if __name__ == "__main__":
    main()
