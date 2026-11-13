"""Export selected syllables as clean WAV clips, spectrogram thumbnails, a contact sheet and credits.

Usage: python3 export.py <wav_dir> <selection.json> <out_dir>
"""
import json, os, sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, stft
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

wav_dir, sel_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(os.path.join(out, "syllables"), exist_ok=True)
sel = json.load(open(sel_path))
sos = butter(4, [1500, 10000], btype="band", fs=44100, output="sos")
cache = {}


def clip(s):
    if s["source"] not in cache:
        sr, x = wavfile.read(os.path.join(wav_dir, s["source"] + ".wav"))
        cache[s["source"]] = (sr, x.astype(np.float64) / 32768.0)
    sr, x = cache[s["source"]]
    a, b = int((s["t0"] - 0.04) * sr), int((s["t1"] + 0.04) * sr)
    y = sosfiltfilt(sos, x[max(0, a):b])
    pad = int(0.032 * sr)  # keep 8 ms either side of the syllable
    y = y[pad:len(y) - pad]
    f = int(0.006 * sr)
    ramp = np.sin(np.linspace(0, np.pi / 2, f)) ** 2
    y[:f] *= ramp; y[-f:] *= ramp[::-1]
    y *= 10 ** (-3 / 20) / (np.abs(y).max() + 1e-12)
    return sr, y


def spec(ax, sr, y):
    f, t, Z = stft(y, sr, nperseg=256, noverlap=224)
    S = 20 * np.log10(np.abs(Z) + 1e-9)
    band = (f >= 1500) & (f <= 9000)
    ax.pcolormesh(t * 1000, f[band] / 1000, S[band], shading="auto", cmap="Greys", vmin=S.max() - 55, vmax=S.max())
    ax.set_ylim(1.5, 9)


rows = int(np.ceil(len(sel) / 8)); fig, axes = plt.subplots(rows, 8, figsize=(16, 2.1 * rows))
for ax in axes.flat[len(sel):]: ax.axis('off')
for ax, s in zip(axes.flat, sel):
    sr, y = clip(s)
    name = f"{s['id']}-{s['source']}.wav"
    wavfile.write(os.path.join(out, "syllables", name), sr, (y * 32767).astype(np.int16))
    s["file"] = "syllables/" + name
    spec(ax, sr, y)
    ax.set_title(f"{s['id']} {s['species'].split()[-1]} · {int(s['dur']*1000)} ms", fontsize=8)
    ax.tick_params(labelsize=6)
    # thumbnail for the web page
    tf, ta = plt.subplots(figsize=(1.6, 0.9), dpi=100)
    spec(ta, sr, y); ta.axis("off"); tf.subplots_adjust(0, 0, 1, 1)
    tf.savefig(os.path.join(out, "syllables", f"{s['id']}-{s['source']}.png"), dpi=100); plt.close(tf)
fig.suptitle("BirdLU bird syllables: B = core, R = reserve. Time (ms) × frequency (kHz)", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(out, "contact-sheet.png"), dpi=110)

for s in sel:
    s.setdefault("watch", "")
keep = ["watch", "id", "species", "scientific", "source", "recordist", "licence", "url", "t0", "t1", "dur",
        "fmean", "fstart", "fend", "wobble", "snr", "quality", "file", "note", "status", "type"]
json.dump([{k: s[k] for k in keep} for s in sel], open(os.path.join(out, "syllables.json"), "w"), indent=1, ensure_ascii=False)

by_src = {}
for s in sel:
    by_src.setdefault(s["source"], []).append(s)
lines = ["# Bird syllable credits", "",
         "Syllables cut from xeno-canto recordings. Each clip is a derivative of the recording below and is",
         "shared under the same licence: **CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/).",
         "Non-commercial only. Any commercial use needs the recordist's permission.", "",
         "| Recording | Species | Recordist | Licence | Syllables |", "|---|---|---|---|---|"]
for src, ss in sorted(by_src.items()):
    s = ss[0]
    lines.append(f"| [{src}]({s['url']}) | {s['species']} (*{s['scientific']}*) | {s['recordist']} | {s['licence']} | "
                 + ", ".join(f"{x['id']} ({x['t0']:.2f}–{x['t1']:.2f} s)" for x in ss) + " |")
lines += ["", "Citation format requested by xeno-canto: *Recordist, XCnnnnnn. Accessible at www.xeno-canto.org/nnnnnn.*"]
open(os.path.join(out, "CREDITS.md"), "w").write("\n".join(lines) + "\n")
print("exported", len(sel))
