"""Find natural trills and clean single notes in full bird recordings.

An element is one continuous sound. A trill is a run of 3+ similar elements the bird repeats by
itself at a steady pace: these keep the bird's own timing, which is what makes them sound alive.
A single note is a short element standing on its own.

Writes lab/out/elements.json and lab/out/elements-<recording>.png (sound picture with every trill
and note boxed and numbered) for picking by eye and ear.

Run:  .venv/bin/python lab/elements.py
"""
import json, os, sys, glob
import numpy as np
import soundfile as sf
from scipy.signal import stft
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from features import picture, active, similarity

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "lab", "sources")
OUT = os.path.join(ROOT, "lab", "out")
N, HOP, F_LO, F_HI = 512, 128, 1200, 10000


def envelope(x, sr):
    f, t, Z = stft(x, sr, nperseg=N, noverlap=N - HOP, boundary=None, padded=False)
    band = (f >= F_LO) & (f <= F_HI)
    P = np.abs(Z[band]) ** 2
    e = 10 * np.log10(P.sum(0) + 1e-14)
    e = np.convolve(e, np.ones(3) / 3, mode="same")
    peak = f[band][np.argmax(P, axis=0)]
    return t, e, peak


def elements(x, sr):
    """Elements are loudness peaks; their edges are the dips around them (or where the sound falls
    12 dB under the peak). Dips, not silences: in fast trills the echo fills the gaps."""
    from scipy.signal import find_peaks
    t, e, peak = envelope(x, sr)
    floor = np.percentile(e, 20)
    frame = HOP / sr
    pk, _ = find_peaks(e, height=floor + 14, prominence=5, distance=max(1, int(0.025 / frame)))
    out = []
    for k, p in enumerate(pk):
        lo = pk[k - 1] if k else 0
        hi = pk[k + 1] if k + 1 < len(pk) else len(e) - 1
        a = lo + int(np.argmin(e[lo:p + 1])) if k else max(0, p - int(0.2 / frame))
        b = p + int(np.argmin(e[p:hi + 1]))
        # tighten to where the element is within 12 dB of its peak
        while a < p and e[a] < e[p] - 12:
            a += 1
        while b > p and e[b] < e[p] - 12:
            b -= 1
        t0, t1 = t[a] - frame, t[b] + frame
        if t1 - t0 < 0.012:
            continue
        out.append(dict(t0=float(t0), t1=float(t1), snr=float(e[p] - floor), f=float(np.median(peak[a:b + 1]))))
    return out


def pic(x, sr, el):
    a, b = int(el["t0"] * sr), int(el["t1"] * sr)
    return active(picture(x[a:b]))


def runs(x, sr, els, max_gap=0.13, min_sim=0.6):
    """Group consecutive similar elements into trills."""
    pics = [pic(x, sr, e) for e in els]
    found, i = [], 0
    while i < len(els):
        j = i
        while (j + 1 < len(els) and els[j + 1]["t0"] - els[j]["t1"] < max_gap
               and similarity(pics[i], pics[j + 1]) >= min_sim
               and abs(np.log2(els[j + 1]["f"] / els[i]["f"])) < 0.25):
            j += 1
        if j - i + 1 >= 3:
            ivals = np.diff([els[k]["t0"] for k in range(i, j + 1)])
            found.append(dict(t0=els[i]["t0"], t1=els[j]["t1"], count=j - i + 1,
                              period=float(np.median(ivals)), steady=float(np.std(ivals) / np.mean(ivals)),
                              elem=float(np.median([els[k]["t1"] - els[k]["t0"] for k in range(i, j + 1)])),
                              f=float(np.median([els[k]["f"] for k in range(i, j + 1)])),
                              snr=float(np.median([els[k]["snr"] for k in range(i, j + 1)])),
                              first=i))
            i = j + 1
        else:
            i += 1
    return found


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {m["id"]: m for m in json.load(open(os.path.join(SRC, "sources.json")))}
    result = {}
    for path in sorted(glob.glob(os.path.join(SRC, "wav", "*.wav"))):
        rid = os.path.basename(path)[:-4]
        x, sr = sf.read(path)
        x = x / (np.max(np.abs(x)) or 1)
        els = elements(x, sr)
        trills = [r for r in runs(x, sr, els) if r["snr"] > 20 and r["steady"] < 0.35]
        in_trill = set()
        for r in trills:
            in_trill.update(range(r["first"], r["first"] + r["count"]))
        singles = []
        for k, e in enumerate(els):
            if k in in_trill or e["snr"] < 25 or not 0.02 < e["t1"] - e["t0"] < 0.16:
                continue
            gap_before = e["t0"] - els[k - 1]["t1"] if k else 9
            gap_after = els[k + 1]["t0"] - e["t1"] if k + 1 < len(els) else 9
            if min(gap_before, gap_after) > 0.06:
                singles.append(e)
        for n, r in enumerate(trills):
            r["id"] = f"{rid}-T{n + 1:02d}"
        for n, e in enumerate(singles):
            e["id"] = f"{rid}-N{n + 1:02d}"
        m = meta[rid]
        result[rid] = dict(species=m["species"], trills=trills, singles=singles)
        print(f"{rid} {m['species']:20s} {len(els):4d} elements, {len(trills):3d} trills, {len(singles):3d} single notes")

        # sound picture with boxes, in strips of 15 s
        dur = len(x) / sr
        strips = int(np.ceil(dur / 15))
        fig, axes = plt.subplots(strips, 1, figsize=(16, 2.6 * strips), squeeze=False)
        f, t, Z = stft(x, sr, nperseg=N, noverlap=N - HOP)
        S = 20 * np.log10(np.abs(Z) + 1e-9)
        for s in range(strips):
            ax = axes[s, 0]
            sel = (t >= 15 * s) & (t < 15 * (s + 1))
            ax.pcolormesh(t[sel], f / 1000, S[:, sel], vmin=S.max() - 70, vmax=S.max(), cmap="Greys", shading="auto")
            ax.set_ylim(1, 10); ax.set_xlim(15 * s, 15 * (s + 1))
            for r in trills:
                if 15 * s <= r["t0"] < 15 * (s + 1):
                    ax.add_patch(plt.Rectangle((r["t0"], 1.2), r["t1"] - r["t0"], 8.5, fill=False, ec="tab:red", lw=1.2))
                    ax.text(r["t0"], 9.4, r["id"][-3:], color="tab:red", fontsize=8)
            for e in singles:
                if 15 * s <= e["t0"] < 15 * (s + 1):
                    ax.add_patch(plt.Rectangle((e["t0"], 1.2), e["t1"] - e["t0"], 8.5, fill=False, ec="tab:blue", lw=0.8))
                    ax.text(e["t0"], 1.4, e["id"][-3:], color="tab:blue", fontsize=7)
        axes[0, 0].set_title(f"{rid} · {m['species']} · red = trills, blue = single notes")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, f"elements-{rid}.png"), dpi=80)
        plt.close(fig)
    json.dump(result, open(os.path.join(OUT, "elements.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
