"""Cut bird recordings into syllables, measure them, and pick the most distinct ones.

Usage: python3 syllables.py <wav_dir> <out_dir> [count]
Writes <out_dir>/candidates.json (every clean syllable) and <out_dir>/selection.json (the picks).
"""
import json, sys, os
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft, medfilt

SOURCES = {
    "XC880931": ("Great Tit", "Parus major", "Lee Alder"),
    "XC376030": ("Great Tit", "Parus major", "Jonathan Tollin"),
    "XC303416": ("Great Tit", "Parus major", "Timo Schnabel"),
    "XC778131": ("Eurasian Blue Tit", "Cyanistes caeruleus", "Paul Driver"),
    "XC637984": ("Eurasian Blue Tit", "Cyanistes caeruleus", "Georg Amann"),
    "XC315114": ("Eurasian Blue Tit", "Cyanistes caeruleus", "Ad Postma"),
    "XC760778": ("European Robin", "Erithacus rubecula", "Benjamin Allegrini"),
    "XC387823": ("European Robin", "Erithacus rubecula", "Brian Henderson"),
    "XC857749": ("European Robin", "Erithacus rubecula", "Olivier Swift, Hélène Cartaud"),
}
LICENCE = "CC BY-NC-SA 4.0"

N, HOP = 512, 128
F_LO, F_HI = 1500, 10000
NPTS = 12  # points in the resampled pitch contour


def load(path):
    sr, x = wavfile.read(path)
    x = x.astype(np.float64) / 32768.0
    return sr, x


def segment(sr, x):
    f, t, Z = stft(x, sr, nperseg=N, noverlap=N - HOP, boundary=None, padded=False)
    P = np.abs(Z) ** 2
    band = (f >= F_LO) & (f <= F_HI)
    Pb, fb = P[band], f[band]
    e = 10 * np.log10(Pb.sum(0) + 1e-14)
    e = np.convolve(e, np.ones(3) / 3, mode="same")
    floor = np.percentile(e, 20)
    on, off = floor + 15, floor + 9
    k = np.argmax(Pb, axis=0)
    # parabolic interpolation of the peak
    pk = np.empty_like(e)
    for i, kk in enumerate(k):
        if 0 < kk < len(fb) - 1:
            a, b, c = np.log(Pb[kk - 1:kk + 2, i] + 1e-14)
            d = a - 2 * b + c
            pk[i] = fb[kk] + (0.5 * (a - c) / d if d < 0 else 0) * (fb[1] - fb[0])
        else:
            pk[i] = fb[kk]
    tonal = 10 * np.log10(Pb.max(0) / (Pb.mean(0) + 1e-14) + 1e-14)  # peak vs band mean, dB
    segs, start, below = [], None, 0
    for i, v in enumerate(e):
        if start is None:
            if v > on: start, below = i, 0
        else:
            if v < off:
                below += 1
                if below >= 4:  # ~12 ms of quiet ends a syllable
                    segs.append((start, i - below)); start = None
            else:
                below = 0
    return dict(t=t, e=e, floor=floor, pk=pk, tonal=tonal, segs=segs, dt=HOP / sr, Pb=Pb, fb=fb)


def describe(sr, x, S, xc):
    out = []
    t, e, pk, tonal, dt = S["t"], S["e"], S["pk"], S["tonal"], S["dt"]
    segs = S["segs"]
    for j, (a, b) in enumerate(segs):
        dur = (b - a + 1) * dt
        if dur < 0.03 or dur > 0.35:
            continue
        idx = np.arange(a, b + 1)
        emax = e[idx].max()
        keep = idx[e[idx] > emax - 18]
        if len(keep) < 6:
            continue
        f = medfilt(pk[keep], 5) if len(keep) >= 5 else pk[keep]
        snr = emax - S["floor"]
        ton = float(np.median(tonal[keep]))
        gap_before = (a - segs[j - 1][1]) * dt if j > 0 else 1.0
        gap_after = (segs[j + 1][0] - b) * dt if j + 1 < len(segs) else 1.0
        # straight-line fit and residual (trill/wobble)
        tt = (keep - keep[0]) * dt
        A = np.vstack([tt, np.ones_like(tt)]).T
        coef, *_ = np.linalg.lstsq(A, f, rcond=None)
        resid = f - A @ coef
        jumps = float(np.mean(np.abs(np.diff(f)) > 400)) if len(f) > 1 else 1.0
        # one clean voice: most of the energy sits within ±350 Hz of the pitch track
        Pb, fb = S["Pb"], S["fb"]
        conc = []
        for i, kf in zip(keep, f):
            col = Pb[:, i]; near = np.abs(fb - kf) <= 350
            conc.append(col[near].sum() / (col.sum() + 1e-14))
        concentration = float(np.median(conc))
        contour = np.interp(np.linspace(0, 1, NPTS), np.linspace(0, 1, len(f)), f)
        seg = dict(
            source=xc, t0=round(float(t[a] - N / 2 / sr), 4), t1=round(float(t[b] + N / 2 / sr), 4),
            dur=round(float(dur), 4), snr=round(float(snr), 1), tonality=round(ton, 1),
            fmean=round(float(f.mean())), fmin=round(float(f.min())), fmax=round(float(f.max())),
            fstart=round(float(f[0])), fend=round(float(f[-1])), slope=round(float(coef[0])),
            wobble=round(float(resid.std())), contour=[round(float(v)) for v in contour],
            gap_before=round(float(gap_before), 3), gap_after=round(float(gap_after), 3),
            jumps=round(jumps, 3), concentration=round(concentration, 3),
        )
        out.append(seg)
    return out


def usable(s):
    # clean = loud, tonal, one continuous pitch track (no jumps between overlapping sounds), isolated
    return (s["snr"] >= 22 and s["tonality"] >= 12 and 2000 <= s["fmean"] <= 7500
            and s["jumps"] <= 0.06 and s["fmax"] - s["fmin"] < 4500 and s["concentration"] >= 0.6
            and s["gap_before"] >= 0.015 and s["gap_after"] >= 0.015)


def distance(a, b):
    ca, cb = np.array(a["contour"]) / 1000, np.array(b["contour"]) / 1000
    d = np.sqrt(((ca - cb) ** 2).mean())                      # pitch shape, kHz
    d += 0.5 * abs(np.log(a["dur"] / b["dur"]))                 # length (varies between renditions)
    d += abs(a["wobble"] - b["wobble"]) / 400                   # trill-ness
    return d


def speaker_score(s):
    """Small speakers and phone mics carry ~2.5-6.5 kHz best."""
    m = s["fmean"]
    return 1.0 if 2500 <= m <= 6000 else 0.7 if m <= 7000 else 0.4


def pick(cands, count):
    # quality score: loud, tonal, speaker-friendly
    for s in cands:
        s["quality"] = round((min(s["snr"], 45) / 45) * 0.4 + (min(s["tonality"], 30) / 30) * 0.2
                             + s["concentration"] * 0.2 + speaker_score(s) * 0.2, 3)
    pool = sorted(cands, key=lambda s: -s["quality"])
    # collapse near-duplicates (a song repeats the same syllable many times): keep the best of each
    reps = []
    for s in pool:
        if all(distance(s, r) > 0.6 for r in reps):
            reps.append(s)
    # farthest-point selection, weighted by quality, keeping species balanced
    species = sorted({SOURCES[s["source"]][1] for s in reps})
    per = {sp: 0 for sp in species}
    cap = int(np.ceil(count / len(species))) + 1
    chosen = [reps[0]]; per[SOURCES[reps[0]["source"]][1]] += 1
    while len(chosen) < count:
        best, bscore = None, -1
        for s in reps:
            if s in chosen or per[SOURCES[s["source"]][1]] >= cap:
                continue
            dmin = min(distance(s, c) for c in chosen)
            sc = min(dmin, 1.5) * s["quality"] ** 2  # distinct enough, then the cleanest wins
            if sc > bscore:
                best, bscore = s, sc
        if best is None:
            break
        best["min_distance"] = round(min(distance(best, c) for c in chosen), 3)
        chosen.append(best); per[SOURCES[best["source"]][1]] += 1
    chosen[0]["min_distance"] = round(min(distance(chosen[0], c) for c in chosen[1:]), 3)
    return reps, chosen


def main():
    wav_dir, out_dir = sys.argv[1], sys.argv[2]
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    os.makedirs(out_dir, exist_ok=True)
    allc = []
    for fn in sorted(os.listdir(wav_dir)):
        xc = fn.split(".")[0]
        sr, x = load(os.path.join(wav_dir, fn))
        S = segment(sr, x)
        c = describe(sr, x, S, xc)
        u = [s for s in c if usable(s)]
        print(f"{xc} {SOURCES[xc][0]:18} {len(S['segs']):4} events  {len(c):4} syllables  {len(u):4} clean")
        allc += u
    reps, chosen = pick(allc, count)
    print(f"\n{len(allc)} clean syllables, {len(reps)} distinct types, {len(chosen)} picked")
    for i, s in enumerate(chosen):
        s["id"] = f"S{i + 1:02d}"
        name, sci, rec = SOURCES[s["source"]]
        s.update(species=name, scientific=sci, recordist=rec, licence=LICENCE,
                 url=f"https://xeno-canto.org/{s['source'][2:]}")
    json.dump(allc, open(os.path.join(out_dir, "candidates.json"), "w"), indent=1)
    json.dump(chosen, open(os.path.join(out_dir, "selection.json"), "w"), indent=1, ensure_ascii=False)
    for s in chosen:
        print(f"{s['id']} {s['species']:18} {s['source']} {s['t0']:7.2f}s {int(s['dur']*1000):4}ms "
              f"{s['fmean']:5}Hz {s['fstart']:5}->{s['fend']:5} wob {s['wobble']:4} snr {s['snr']:5} conc {s['concentration']} q {s['quality']} d {s.get('min_distance')}")


if __name__ == "__main__":
    main()
