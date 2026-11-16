"""Nightingale phrases to listen to before choosing a new opening and closing (Gab, 16 Nov: "Let me listen
the opening and the closing before we start building the synthesizer").

Three Common Nightingale recordings (lab/fetch_sources.py: XC138451, XC473316, XC546043, CC BY-SA 4.0).
Each is cut into its song phrases: sound in the 1.2–9 kHz band louder than 12 dB above the recording's
quiet 20 %, smoothed over ~0.1 s, pieces less than 0.35 s apart joined. Phrases of 1.2 s or more are kept,
cleaned of the recording's background like every other source (lab/sketch.py, cut: spectral gating,
level-matched, soft edges). These are the recordings themselves, for listening only: nothing is
synthesized yet.

Writes birds/nightingale/<id>-<k>.wav and birds/nightingale/phrases.json.
Run:  .venv/bin/python lab/nightingale.py
"""
import json, os, sys
import numpy as np
import soundfile as sf
from scipy.signal import stft

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sketch import cut, SR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "birds", "nightingale")
IDS = ["XC138451", "XC473316", "XC546043"]
MIN_LEN = 1.2


def phrases(y):
    f, t, Z = stft(y, SR, nperseg=1024, noverlap=512)
    band = (f > 1200) & (f < 9000)
    e = 10 * np.log10((np.abs(Z[band]) ** 2).sum(0) + 1e-12)
    e = np.convolve(e, np.ones(9) / 9, mode="same")
    on = e > np.percentile(e, 20) + 12
    segs, s, last = [], None, None
    for i, o in enumerate(on):
        if o:
            s = i if s is None else s
            last = i
        elif s is not None and t[i] - t[last] > 0.35:
            segs.append((t[s], t[last])); s = None
    if s is not None:
        segs.append((t[s], t[last]))
    return [(a, b) for a, b in segs if b - a >= MIN_LEN]


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "lab", "sources", "sources.json")))}
    out = []
    for rec, rid in enumerate(IDS, 1):
        y, sr = sf.read(os.path.join(ROOT, "lab", "sources", "wav", rid + ".wav"))
        assert sr == SR
        for k, (a, b) in enumerate(phrases(y), 1):
            x, _ = cut((rid, round(max(0, a - 0.08), 3), round(b + 0.15, 3)))
            fn = f"{rid}-{k}.wav"
            sf.write(os.path.join(OUT, fn), x, SR, subtype="PCM_16")
            out.append(dict(file=fn, recording=rec, id=rid, phrase=k, t0=round(a, 2), t1=round(b, 2),
                            dur=round(len(x) / SR, 2), recordist=meta[rid]["recordist"], licence=meta[rid]["licence"],
                            url=meta[rid]["commons"]))
        print(rid, sum(1 for o in out if o["id"] == rid), "phrases")
    json.dump(out, open(os.path.join(OUT, "phrases.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
