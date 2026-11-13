"""Step 1: which bird syllables stay distinct after a speaker, a room and distance?

For each condition, every syllable is sent through the simulated sound path many times, cut out
(with some slop around its edges, like a real cutter), and matched to the nearest clean syllable.
Outputs, in lab/out/:
  similarity.png   how alike the clean syllables are, pair by pair
  confusion-*.png  what each syllable was heard as, per condition
  distinct.txt     accuracy per syllable and condition, and the pairs that get mixed up

Run:  .venv/bin/python lab/distinct.py [trials]
Segmentation here is ideal (the true position is known); the real cutter adds its own errors.
"""
import json, sys, os
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from channel import transmit, SR
from features import picture, active, similarity

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "lab", "out")

QUIET = [("hiss", 35)]
CONDITIONS = {
    "near 0.4 m":       dict(distance=0.4, rt60=0.5, critical=0.6, noise=QUIET),
    "room 1 m":         dict(distance=1.0, rt60=0.5, critical=0.6, noise=QUIET),
    "room 1.5 m":       dict(distance=1.5, rt60=0.5, critical=0.6, noise=QUIET),
    "room 2 m":         dict(distance=2.0, rt60=0.5, critical=0.6, noise=QUIET),
    "room 3 m":         dict(distance=3.0, rt60=0.5, critical=0.6, noise=QUIET),
    "hall 1.5 m":       dict(distance=1.5, rt60=1.6, critical=2.5, noise=QUIET),
    "hall 3 m":         dict(distance=3.0, rt60=1.6, critical=2.5, noise=QUIET),
    "street 1.5 m":     dict(distance=1.5, rt60=0.3, critical=3.0, noise=[("traffic", 15), ("hiss", 35)]),
    "station 2 m":      dict(distance=2.0, rt60=1.2, critical=2.0, noise=[("traffic", 12), ("voices", 18), ("hiss", 35)]),
}


def load():
    meta = json.load(open(os.path.join(ROOT, "birds", "syllables.json")))
    clips = {}
    for s in meta:
        x, sr = sf.read(os.path.join(ROOT, "birds", s["file"]))
        assert sr == SR, (s["id"], sr)
        if x.ndim > 1:
            x = x.mean(axis=1)
        clips[s["id"]] = x / (np.max(np.abs(x)) or 1)
    return meta, clips


def heard(x, cond, seed, rng):
    pad = np.zeros(int(0.15 * SR))
    y = transmit(np.concatenate([pad, x, pad]), cond, SR, seed)
    # cut around the true position with 0–15 ms of slop on each side
    a = len(pad) - int(rng.uniform(0, 0.015) * SR)
    b = len(pad) + len(x) + int(rng.uniform(0, 0.015) * SR)
    return active(picture(y[a:b]))


def main(trials=20):
    os.makedirs(OUT, exist_ok=True)
    meta, clips = load()
    ids = [s["id"] for s in meta]
    ref = {i: active(picture(clips[i])) for i in ids}
    n = len(ids)

    # 1. how alike the clean syllables are
    sim = np.array([[similarity(ref[a], ref[b]) for b in ids] for a in ids])
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(sim, vmin=0, vmax=1, cmap="magma")
    ax.set_xticks(range(n), ids, rotation=90); ax.set_yticks(range(n), ids)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{sim[i, j]:.2f}"[1:], ha="center", va="center", fontsize=6,
                    color="black" if sim[i, j] > 0.6 else "white")
    ax.set_title("How alike the clean syllables are (1 = identical)")
    fig.colorbar(im); fig.tight_layout(); fig.savefig(os.path.join(OUT, "similarity.png"), dpi=110)
    plt.close(fig)

    lines = ["Clean syllables, most alike pairs:"]
    pairs = sorted(((sim[i, j], ids[i], ids[j]) for i in range(n) for j in range(i + 1, n)), reverse=True)
    for v, a, b in pairs[:8]:
        lines.append(f"  {a}-{b}  {v:.2f}")

    # 2. what each syllable is heard as, per condition
    rng = np.random.default_rng(1)
    table = {}
    for cname, cond in CONDITIONS.items():
        conf = np.zeros((n, n), int)
        margins = {i: [] for i in ids}
        for si, sid in enumerate(ids):
            for t in range(trials):
                h = heard(clips[sid], cond, seed=1000 * si + t, rng=rng)
                scores = np.array([similarity(h, ref[r]) for r in ids])
                order = np.argsort(scores)[::-1]
                conf[si, order[0]] += 1
                margins[sid].append(scores[si] - max(scores[k] for k in range(n) if k != si))
        table[cname] = (conf, margins)
        acc = np.trace(conf) / conf.sum()
        print(f"{cname:16s} {100 * acc:5.1f}% recognised")

        fig, ax = plt.subplots(figsize=(7, 6))
        ax.imshow(conf / trials, vmin=0, vmax=1, cmap="Greens")
        ax.set_xticks(range(n), ids, rotation=90); ax.set_yticks(range(n), ids)
        ax.set_xlabel("heard as"); ax.set_ylabel("sung")
        ax.set_title(f"{cname}: {100 * acc:.0f}% recognised")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, f"confusion-{cname.replace(' ', '-').replace('.', '')}.png"), dpi=100)
        plt.close(fig)

    lines.append("")
    lines.append(f"Recognised, per syllable and condition ({trials} tries each). Margin = how far ahead")
    lines.append("of the next best match the right syllable stays, median (negative = usually lost).")
    head = "      " + "".join(f"{c[:11]:>12s}" for c in CONDITIONS)
    lines.append(head)
    for si, sid in enumerate(ids):
        row = f"{sid:6s}"
        for cname in CONDITIONS:
            conf, margins = table[cname]
            row += f"{100 * conf[si, si] / trials:7.0f}%{np.median(margins[sid]):+5.2f}"
        lines.append(row)
    row = "all   "
    for cname in CONDITIONS:
        conf, _ = table[cname]
        row += f"{100 * np.trace(conf) / conf.sum():7.0f}%     "
    lines.append(row)

    lines.append("")
    lines.append("Most frequent mix-ups over all conditions (sung -> heard as: times):")
    total = sum(t[0] for t in table.values())
    off = sorted(((total[i, j], ids[i], ids[j]) for i in range(n) for j in range(n) if i != j), reverse=True)
    for c, a, b in off[:12]:
        if c:
            lines.append(f"  {a} -> {b}: {c}")
    txt = "\n".join(lines)
    open(os.path.join(OUT, "distinct.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
