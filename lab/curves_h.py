"""Version H: version G with the notes spaced for an echoing room (MUSICOLOGY.md, step 12).

Real test v11 far (4–5 m, living room, echo about 1 s): 10.2 % wrong, and every consonant swap was between
letters 0 or 1 semitone apart (t→p three times on D8, d→q on F7, s→d, q→h, c→f, r→l). In a long echo the curve
is smeared and the note has to keep letters apart. Gab, 16 Nov: "yes, commit G then build H".

Rules
  - The 13 most used consonants (n s t r l d c h m p g b v, five languages) each get a note of their own, on a
    whole-tone grid from E6 to E8 (1319–5274 Hz, under Gab's 5.5 kHz): E6 F#6 G#6 A#6 C7 D7 E7 F#7 G#7 A#7 C8
    D8 E8. So any two of them are at least 2 semitones apart.
  - The 7 rarest (f w q z k j x) sit on one of those notes too, sharing it with a more used letter; the curve
    and texture keep them apart (a rare letter is rarely sung, so its occasional swap costs little).
  - Texture (chip, buzz, hum, glide, roll) and curves as in G (lab/curves.py).
Cost: as in G (lab/curves.py), with the guide's echo at 1.0 s (the room of v11 far).
Search: move a letter to another curve or note (a used letter swaps note with the one there), until nothing
lowers the cost; 12 seeded random starts; the best is kept.

Writes birds/variants/spaced/<letter>.wav, version "spaced" in birds/variants/variants.json, birds/curves-h.json.
Run:  .venv/bin/python lab/curves_h.py   (after lab/gestures.py; takes several minutes)
"""
import json, os, sys, time
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, OUT, ROOT
from gestures import GROUP
from sketch import SR
from decode import match, load_voice
from likeness import room
from curves import CURVES, build, picture, note_name

SLOTS = list(range(88, 113, 2))          # E6 .. E8, whole tones
RARE = list("fwqzkjx")
RT60 = 1.0
STARTS = 12


def main():
    t0 = time.time()
    h = room(SR, RT60)
    M = models()
    cons = sorted(GROUP)
    used = [c for c in cons if c not in RARE]
    assert len(used) == len(SLOTS)
    grp = {c: ("glide" if GROUP[c].startswith("glide") else GROUP[c]) for c in cons}
    vd, snd_d, _ = load_voice(os.path.join(ROOT, "birds", "voices", "nightingale-d"))
    fixed = list("aeiouy") + ["#", "@"]
    cand, pics, tpls = [], [], []
    for c in cons:
        for k in CURVES:
            for n in SLOTS:
                P, T = picture(build(M[c], grp[c], k, n, seed=ord(c)), h)
                cand.append((c, k, n)); pics.append(P); tpls.append(T)
    fpics, ftpls = zip(*[picture(snd_d[f], h) for f in fixed])
    print(f"{len(cand)} candidates in {time.time() - t0:.0f} s", flush=True)
    N = len(cand)
    at = {cn: i for i, cn in enumerate(cand)}
    like = lambda P1, T1, P2, T2: max(match(P1, T2).max(), match(P2, T1).max())
    LF = np.array([[like(pics[i], tpls[i], fpics[j], ftpls[j]) for j in range(len(fixed))] for i in range(N)], dtype=np.float32)
    LC = np.zeros((N, N), dtype=np.float32)
    for i in range(N):
        ci, _, ni = cand[i]
        for j in range(i + 1, N):
            cj, _, nj = cand[j]
            if ci != cj and abs(ni - nj) <= 10:
                LC[i, j] = LC[j, i] = like(pics[i], tpls[i], pics[j], tpls[j])
    print(f"likeness table in {time.time() - t0:.0f} s", flush=True)

    B = json.load(open(os.path.join(ROOT, "birds", "bigrams.json")))
    fr = lambda x: B["letters"].get(x, 0.002)
    share = {}
    for p in B["pairs"]:
        a, b = p["pair"]
        if a != b:
            share[(a, b)] = share.get((a, b), 0) + p["mean"]; share[(b, a)] = share.get((b, a), 0) + p["mean"]
    vow_note = {c: 69 + 12 * np.log2(json.load(open(os.path.join(OUT, "variants.json")))["versions"]["gesture"][c]["main"] / 440)
                for c in "aeiouy"}
    pen = lambda L: 100 * np.maximum(0, L - 0.5) ** 2

    def cost(sel):
        total = 0.0
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

    def moved(sel, c, k, n):
        """sel with c on curve k, note n; a used letter already on n takes c's old note."""
        s = dict(sel)
        if c in used:
            for b in used:
                if b != c and cand[s[b]][2] == n:
                    s[b] = at[(b, cand[s[b]][1], cand[s[c]][2])]
        s[c] = at[(c, k, n)]
        return s

    rng = np.random.default_rng(12)
    best = None
    for st in range(STARTS):
        notes = rng.permutation(SLOTS)
        sel = {c: at[(c, rng.choice(list(CURVES)), int(notes[i]))] for i, c in enumerate(used)}
        sel.update({c: at[(c, rng.choice(list(CURVES)), int(rng.choice(SLOTS)))] for c in RARE})
        cur = cost(sel)
        improved = True
        while improved:
            improved = False
            for c in rng.permutation(cons):
                for k in CURVES:
                    for n in SLOTS:
                        s2 = moved(sel, c, k, n)
                        c2 = cost(s2)
                        if c2 < cur - 1e-9:
                            cur, sel, improved = c2, s2, True
        print(f"start {st + 1}: cost {cur:.3f}", flush=True)
        if best is None or cur < best[0]:
            best = (cur, dict(sel))
    cur, sel = best
    notes_used = sorted(cand[sel[c]][2] for c in used)
    assert notes_used == SLOTS, notes_used

    info = json.load(open(os.path.join(OUT, "variants.json")))
    os.makedirs(os.path.join(OUT, "spaced"), exist_ok=True)
    info["versions"]["spaced"] = {}
    D = info["versions"]["gesture"]
    for ch in M:
        if ch in GROUP:
            c, k, n = cand[sel[ch]]
            y = build(M[ch], grp[ch], k, n, seed=ord(ch))
            changed, main_hz = f"{GROUP[ch]}, {k}, {note_name(n)}", round(440 * 2 ** ((n - 69) / 12))
        else:
            y = sf.read(os.path.join(OUT, D[ch]["file"]))[0]
            changed, main_hz = "as D", D[ch]["main"]
        sf.write(os.path.join(OUT, "spaced", f"{ch}.wav"), y, SR, subtype="PCM_16")
        info["versions"]["spaced"][ch] = dict(file=f"spaced/{ch}.wav", dur=round(len(y) / SR, 4), main=main_hz, changed=changed)
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)
    out = {c: dict(group=GROUP[c], curve=cand[sel[c]][1], note=note_name(cand[sel[c]][2]), rare=c in RARE) for c in cons}
    json.dump(dict(cost=round(cur, 3), rt60=RT60, slots=[note_name(n) for n in SLOTS], consonants=out),
              open(os.path.join(ROOT, "birds", "curves-h.json"), "w"), ensure_ascii=False, indent=1)
    for c in sorted(cons, key=lambda c: (cand[sel[c]][2], c in RARE)):
        print(f"  {c}  {out[c]['note']:4s} {out[c]['curve']:7s} ({GROUP[c]}){'  rare' if c in RARE else ''}")
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
