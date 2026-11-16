"""A partition: every letter on a note of its own, letters that clash on opposite sides (MUSICOLOGY.md, step 15).

Gab, 16 Nov, looking at version D on a staff: things "are sitting exactly on the same note. That's why it's wrong
since the beginning." His rule from the start of the musicology branch: the most used letter pairs (five languages,
lab/bigrams.py) and the letters that can be confused sit on opposite sides of the range.

Notes: 26 places evenly spaced over three octaves, C5 (523 Hz) to C8 (4186 Hz), 1.44 semitones apart, one letter
each (Gab: "for 3 octaves"; OCTAVES=2 gives two octaves).
Cost, lowest wins, only Gab's rule:
  sum over letter pairs of  share of the pair in the five languages × max(0, 12 − semitones apart) / 12
  + 10 for each pair confused (real tests v9, v10, v11, Gab's ear; a/o on the same note in D) less than 7 apart
Search: swap two letters whenever it lowers the cost, from 200 seeded random starts.
Writes birds/partition.json and lab/out/partition-new.png (staff). Run:  .venv/bin/python lab/partition.py
"""
import json, os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trill_voice import CONFUSED

LETTERS = list("abcdefghijklmnopqrstuvwxyz")
OCTAVES = int(os.environ.get("OCTAVES", "3"))
LOW = 108 - 12 * OCTAVES                # C8 at the top; 3 octaves: C5 (523 Hz) .. C8 (4186 Hz)
NOTES = [LOW + 12 * OCTAVES * k / 25 for k in range(26)]   # 26 letters evenly spaced (3 octaves: 1.44 semitones apart)
CONF = {tuple(sorted(p)) for p in CONFUSED + [("a", "o")]}
STARTS = 200
NAT = {0: "C", 2: "D", 4: "E", 5: "F", 7: "G", 9: "A", 11: "B"}
STEP = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


def name(m):
    m = int(round(m)); pc = m % 12; sharp = pc not in NAT; n = NAT[pc - 1] if sharp else NAT[pc]
    return n + ("♯" if sharp else ""), m // 12 - 1, sharp, (m // 12 - 1) * 7 + STEP[n]


def main():
    B = json.load(open(os.path.join(ROOT, "birds", "bigrams.json")))
    idx = {c: i for i, c in enumerate(LETTERS)}
    W = np.zeros((26, 26))
    for p in B["pairs"]:
        a, b = p["pair"]
        if a != b and a in idx and b in idx:
            W[idx[a], idx[b]] += p["mean"]; W[idx[b], idx[a]] += p["mean"]
    C = np.zeros((26, 26))
    for a, b in CONF:
        C[idx[a], idx[b]] = C[idx[b], idx[a]] = 1

    def cost(pos):
        d = np.abs(pos[:, None] - pos[None, :])
        return float((W * np.maximum(0, 12 - d) / 12).sum() / 2 + 10 * (C * (d < 7)).sum() / 2)

    rng = np.random.default_rng(17)
    best = None
    for s in range(STARTS):
        pos = np.array(rng.permutation(NOTES), dtype=float)
        cur = cost(pos); improved = True
        while improved:
            improved = False
            for i in range(26):
                for j in range(i + 1, 26):
                    pos[i], pos[j] = pos[j], pos[i]
                    c2 = cost(pos)
                    if c2 < cur - 1e-12:
                        cur, improved = c2, True
                    else:
                        pos[i], pos[j] = pos[j], pos[i]
        if best is None or cur < best[0]:
            best = (cur, pos.copy())
    cur, pos = best
    note = {c: float(pos[idx[c]]) for c in LETTERS}
    d = np.abs(pos[:, None] - pos[None, :])
    top = sorted(((W[i, j], LETTERS[i] + LETTERS[j], int(d[i, j])) for i in range(26) for j in range(i + 1, 26)), reverse=True)[:12]
    json.dump(dict(cost=round(cur, 3), midi={c: round(note[c], 2) for c in LETTERS}, notes={c: f"{name(note[c])[0]}{name(note[c])[1]}" for c in LETTERS},
                   hz={c: round(440 * 2 ** ((note[c] - 69) / 12)) for c in LETTERS}),
              open(os.path.join(ROOT, "birds", "partition.json"), "w"), ensure_ascii=False, indent=1)
    print("most used pairs, semitones apart:", ", ".join(f"{p} {k}" for _, p, k in top))
    print("confused pairs:", ", ".join(f"{a}{b} {abs(note[a] - note[b]):.1f}" for a, b in sorted(CONF)))

    letters = sorted(LETTERS, key=lambda c: note[c])
    lo = name(NOTES[0])[3]; hi = name(NOTES[-1])[3] + 2; lo -= lo % 2
    fig, ax = plt.subplots(figsize=(17, 8))
    names = ["C", "D", "E", "F", "G", "A", "B"]
    for s in range(lo, hi + 1):
        if s % 2 == 0:
            ax.plot([0, 27], [s, s], color="#444", lw=1.1, zorder=0)
        ax.text(-0.15, s, f"{names[s % 7]}{s // 7}", ha="right", va="center", fontsize=9, color="#666")
    for i, c in enumerate(letters):
        nm, octv, sharp, s = name(note[c]); x = i + 1; col = "#c0392b" if c in "aeiouy" else "#1f5f99"
        ax.add_patch(Ellipse((x, s), 0.55, 1.6, angle=-20, color=col, zorder=3))
        if sharp:
            ax.text(x - 0.42, s, "♯", ha="center", va="center", fontsize=15, color=col)
        ax.text(x, lo - 2.2, c, ha="center", va="center", fontsize=20, fontweight="bold", color=col)
        ax.text(x, lo - 3.6, f"{nm}{octv}", ha="center", va="center", fontsize=8.5, color="#555")
        ax.text(x, lo - 4.6, f"{440 * 2 ** ((note[c] - 69) / 12):.0f}", ha="center", va="center", fontsize=7.5, color="#888")
    ax.text(0.2, lo - 4.6, "Hz", ha="right", va="center", fontsize=7.5, color="#888")
    ax.set_xlim(-1.3, 28); ax.set_ylim(lo - 5.5, hi + 1.5); ax.axis("off")
    ax.set_title(f"Proposed: every letter on a place of its own over {OCTAVES} octaves. Most used pairs and confused letters far apart. "
                 "Red = vowels, blue = consonants.", fontsize=11, loc="left")
    plt.tight_layout(); plt.savefig(os.path.join(ROOT, "lab", "out", "partition-new.png"), dpi=80)


if __name__ == "__main__":
    main()
