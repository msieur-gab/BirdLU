"""A bird synthesizer learned from real trills: original → copy → model.

copy   the trill's own pitch line, loudness and overtones measured every 1.5 ms, rebuilt from pure
       tones. Shows whether clean synthesis can sound like this bird at all.
model  the trill described by a few numbers: the shape of one note (pitch and loudness at 24 points),
       its overtones, how many notes, how fast, and how pitch and loudness drift from note to note.
       Rebuilt from those numbers only, with a little natural wobble. This is the synthesizer.

Writes birds/synth/<letter>-{original,copy,model}.wav, <letter>.png (three sound pictures),
birds/synth/voices.json (the model numbers: what a phone or an ESP32 would need to sing them).

Run:  .venv/bin/python lab/synth.py
"""
import json, os, sys
import numpy as np
import soundfile as sf
from scipy.signal import stft, find_peaks, medfilt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from sketch import VOWELS, CONSONANTS, cut, SR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "birds", "synth")
NFFT, HOP = 1024, 64          # fine time steps (1.45 ms), fine pitch (bins + interpolation)
F_LO, F_HI = 1200, 10000
NPTS = 24                     # points describing one note
HARM = 3                      # fundamental + 2 overtones


# ---------- analysis ----------

def track(x):
    """Per frame: time, pitch (Hz) of the strongest ridge, and amplitude of harmonics 1..HARM."""
    f, t, Z = stft(x, SR, nperseg=NFFT, noverlap=NFFT - HOP, boundary=None, padded=False)
    M = np.abs(Z)
    band = (f >= F_LO) & (f <= F_HI)
    idx = np.where(band)[0]
    k = idx[np.argmax(M[band], axis=0)]
    pitch = np.empty(len(t))
    for i, kk in enumerate(k):
        a, b, c = np.log(M[kk - 1:kk + 2, i] + 1e-12)
        d = a - 2 * b + c
        pitch[i] = (kk + (0.5 * (a - c) / d if d < 0 else 0)) * SR / NFFT
    amps = np.zeros((HARM, len(t)))
    win_gain = NFFT / 4  # Hann window: amplitude of a sinusoid in the STFT ≈ A * N/4
    for h in range(1, HARM + 1):
        kh = np.clip(np.round(pitch * h * NFFT / SR).astype(int), 1, len(f) - 2)
        amps[h - 1] = np.max(np.stack([M[kh - 1, np.arange(len(t))], M[kh, np.arange(len(t))], M[kh + 1, np.arange(len(t))]]), axis=0) / win_gain
    amps[1:][pitch[None, :].repeat(HARM - 1, 0) * np.arange(2, HARM + 1)[:, None] > SR / 2 - 500] = 0
    return t, pitch, amps


def synthesize(t_frames, pitch, amps, n, jitter=None):
    """Additive synthesis: phase-accumulated sine for each harmonic, parameters interpolated per sample."""
    ts = np.arange(n) / SR
    f = np.interp(ts, t_frames, pitch)
    if jitter is not None:
        f = f * (1 + jitter)
    phase = 2 * np.pi * np.cumsum(f) / SR
    y = np.zeros(n)
    for h in range(HARM):
        a = np.interp(ts, t_frames, amps[h], left=0, right=0)
        y += a * np.sin((h + 1) * phase)
    return y


def copy_of(x):
    t, p, A = track(x)
    gate = A[0] > A[0].max() * 10 ** (-40 / 20)   # silence outside the notes
    p = medfilt(p, 5)
    A = A * gate
    return synthesize(t, p, A, len(x))


def notes_of(t, p, A):
    """Cut the track into notes. A note ends where the sound falls quiet, dips by 6 dB, or the pitch
    jumps (a wren never pauses: each new note starts with a sudden leap)."""
    a = 20 * np.log10(A[0] + 1e-9)
    a_s = np.convolve(a, np.ones(5) / 5, mode="same")
    ref = np.percentile(a_s, 97)  # not the max: a single click would hide the notes
    on = a_s > ref - 22
    cuts = set()
    dips, _ = find_peaks(-a_s, prominence=6)
    cuts.update(int(d) for d in dips)
    jump = np.abs(np.diff(np.log2(np.maximum(p, 1)))) > 0.18
    cuts.update(int(i) + 1 for i in np.where(jump & on[1:] & on[:-1])[0])
    notes, s = [], None
    min_len = int(0.012 * SR / HOP)
    for i in range(len(a_s)):
        if s is None:
            if on[i]:
                s = i
        elif not on[i] or i in cuts:
            if i - s >= min_len:
                notes.append((s, i - 1))
            s = i if on[i] else None
    if s is not None and len(a_s) - s >= min_len:
        notes.append((s, len(a_s) - 1))
    return notes


def model_of(x):
    """A few numbers that describe the trill, found by folding: a trill repeats, so its period is
    found from how its loudness repeats, and all cycles are laid on top of each other. The typical
    cycle (median, so stray noise and tracker slips drop out) is the note."""
    t, p, A = track(x)
    p = medfilt(p, 5)
    a = A[0] / (np.percentile(A[0], 97) + 1e-12)
    # 1. period: first strong peak of the loudness autocorrelation, between 20 and 400 ms
    z = a - a.mean()
    ac = np.correlate(z, z, mode="full")[len(z) - 1:]
    ac /= ac[0] + 1e-12
    lo, hi = int(0.02 * SR / HOP), min(len(ac) - 1, int(0.4 * SR / HOP))
    pk, _ = find_peaks(ac[lo:hi], height=0.2)
    P = (lo + pk[0]) if len(pk) else (lo + int(np.argmax(ac[lo:hi])))
    # 2. phase: start each cycle at its quietest moment, so the note sits in the middle
    n_cyc = max(1, len(a) // P)
    folded = np.median(a[: n_cyc * P].reshape(n_cyc, P), axis=0)
    phase = int(np.argmin(np.convolve(folded, np.ones(5) / 5, mode="same")))
    cycles = [(phase + k * P, phase + (k + 1) * P) for k in range(n_cyc + 1) if phase + (k + 1) * P <= len(a)]
    # 3. typical cycle
    pts = 2 * NPTS
    u = np.linspace(0, 1, pts)
    shapes, envs, levels, centres, harm = [], [], [], [], []
    for s, e in cycles:
        uu = np.linspace(0, 1, e - s)
        env = a[s:e]
        loud = env > env.max() * 0.25
        centre = float(2 ** np.average(np.log2(p[s:e][loud]), weights=env[loud])) if loud.any() else float(np.median(p[s:e]))
        shapes.append(np.interp(u, uu, np.log2(p[s:e] / centre)))
        envs.append(np.interp(u, uu, env))
        levels.append(float(env.max())); centres.append(centre)
        harm.append([float(np.median((A[h, s:e] / (A[0, s:e] + 1e-12))[loud])) if loud.any() else 0.0 for h in range(1, HARM)])
    env = np.median(envs, axis=0)
    env = env / (env.max() + 1e-12)
    env[env < 0.03] = 0
    shape = np.median(shapes, axis=0)
    # where the note is silent, its pitch is meaningless: hold the nearest sounding value
    sounding = env > 0.08
    if sounding.any():
        idx = np.where(sounding)[0]
        shape = np.interp(np.arange(pts), idx, shape[idx])
    k = np.arange(len(cycles))
    fit = lambda v: float(np.polyfit(k, v, 1)[0]) if len(cycles) > 2 else 0.0
    return dict(
        notes=max(len(cycles), int(round(len(a) / P))),  # sing as many notes as the bird did
        period=round(P * HOP / SR, 4),
        note_dur=round(P * HOP / SR, 4),  # a cycle: the note and the breath after it
        pitch=round(float(np.median(centres))),
        shape=[round(float(v), 4) for v in shape],
        env=[round(float(v), 3) for v in env],
        overtones=[round(float(v), 3) for v in np.median(harm, axis=0)],
        # drift across the notes: pitch in octaves per note, level in dB per note
        pitch_drift=round(fit(np.log2(centres)), 5),
        level_drift=round(fit(20 * np.log10(np.array(levels) + 1e-9)), 3),
        accel=0.0,
    )


# ---------- synthesis from the model (this is what a phone or an ESP32 would run) ----------

def sing(m, seed=0, wobble=0.004):
    rng = np.random.default_rng(seed)
    u = np.linspace(0, 1, len(m["shape"]))
    total = m["period"] * (m["notes"] - 1) + m["note_dur"] + 0.05
    n = int(total * SR)
    y = np.zeros(n)
    t_start = 0.0
    for i in range(m["notes"]):
        centre = m["pitch"] * 2 ** (m["pitch_drift"] * i + rng.normal(0, 0.006))
        level = 10 ** ((m["level_drift"] * i + rng.normal(0, 0.8)) / 20)
        dur = m["note_dur"] * (1 + rng.normal(0, 0.03))
        k = int(dur * SR)
        tt = np.linspace(0, 1, k)
        f = centre * 2 ** np.interp(tt, u, m["shape"])
        # a slow random wobble: real voices never hold a perfectly clean line
        w = np.convolve(rng.normal(0, 1, k), np.ones(200) / 200, mode="same")
        f = f * (1 + wobble * w / (np.std(w) + 1e-9))
        env = np.interp(tt, u, m["env"]) * level
        r = min(int(0.003 * SR), k // 4)  # soft edges: no clicks between notes
        if r > 0:
            env[:r] *= np.sin(np.linspace(0, np.pi / 2, r)) ** 2
            env[-r:] *= np.cos(np.linspace(0, np.pi / 2, r)) ** 2
        phase = 2 * np.pi * np.cumsum(f) / SR
        note = env * np.sin(phase)
        for h, r in enumerate(m["overtones"], start=2):
            if centre * h < SR / 2 - 500:
                note += env * r * np.sin(h * phase)
        o = int(t_start * SR)
        y[o:o + k] += note[: max(0, min(k, n - o))]
        t_start += m["period"] + m["accel"] * i
    return y


# ---------- single notes (consonants) ----------

def note_model(x):
    """One note: its sounding part, pitch line and loudness at 48 points, overtones."""
    t, p, A = track(x)
    p = medfilt(p, 5)
    a = A[0] / (np.percentile(A[0], 97) + 1e-12)
    on = np.where(a > 10 ** (-28 / 20))[0]
    s, e = (on[0], on[-1]) if len(on) > 1 else (0, len(a) - 1)
    pts = 2 * NPTS
    uu, u = np.linspace(0, 1, e - s + 1), np.linspace(0, 1, pts)
    env = np.interp(u, uu, a[s:e + 1])
    env = env / (env.max() + 1e-12)
    loud = a[s:e + 1] > 0.25
    centre = float(2 ** np.average(np.log2(p[s:e + 1][loud]), weights=a[s:e + 1][loud])) if loud.any() else float(np.median(p[s:e + 1]))
    shape = np.interp(u, uu, np.log2(p[s:e + 1] / centre))
    dur = float(t[e] - t[s]) + HOP / SR
    return dict(notes=1, period=round(dur, 4), note_dur=round(dur, 4), pitch=round(centre),
                shape=[round(float(v), 4) for v in shape], env=[round(float(v), 3) for v in env],
                overtones=[round(float(np.median((A[h, s:e + 1] / (A[0, s:e + 1] + 1e-12))[loud])) if loud.any() else 0.0, 3)
                           for h in range(1, HARM)],
                pitch_drift=0.0, level_drift=0.0, accel=0.0)


def trim(y, below_db=40, keep_ms=3):
    """Drop the near-silence before the first note and after the last one (a trill's last
    'breath'), so the gap between letters is the gap the timing says, nothing hidden."""
    env = np.convolve(np.abs(y), np.ones(64) / 64, mode="same")
    on = np.where(env > env.max() * 10 ** (-below_db / 20))[0]
    if not len(on):
        return y
    k = int(keep_ms / 1000 * SR)
    return y[max(0, on[0] - k): on[-1] + k]


def brisken(m, vowel, trill_len=0.28, tempo=0.82, max_note=0.12):
    """A quicker way of singing the same voice: trills a little faster and only 2-3 notes long,
    long consonant notes shortened. The shape of each note is unchanged."""
    m = dict(m)
    if vowel:
        m["period"] = m["note_dur"] = round(m["period"] * tempo, 4)
        m["notes"] = int(min(m["notes"], max(2, round(trill_len / m["period"]))))
    elif m["note_dur"] > max_note:
        m["period"] = m["note_dur"] = max_note
    return m


def synth_pieces(brisk=False):
    """Every letter sung by the synthesizer: vowels from trill models, consonants from note models.
    Level-matched like the recorded cuts, so the sketch's phrasing stays the same."""
    pieces = {}
    for ch, spec in {**VOWELS, **CONSONANTS}.items():
        x, src = cut(spec)
        m = model_of(norm(x)) if ch in VOWELS else note_model(norm(x))
        if brisk:
            m = brisken(m, ch in VOWELS)
        y = trim(sing(m, seed=ord(ch)))
        loud = np.sort(np.abs(y))[-max(1, len(y) // 5):]
        y = y / (np.sqrt(np.mean(loud ** 2)) + 1e-9) * 0.25
        pieces[ch] = (y, dict(src, kind="synth", id="voice modelled on " + src["id"]))
    return pieces


def synth_frames():
    from sketch import FRAMES
    out = {}
    for k, spec in FRAMES.items():
        x, src = cut(spec)
        y = sing(note_model(norm(x)), seed=len(k))
        loud = np.sort(np.abs(y))[-max(1, len(y) // 5):]
        out[k] = (y / (np.sqrt(np.mean(loud ** 2)) + 1e-9) * 0.25, dict(src, kind="synth"))
    return out


# ---------- outputs ----------

def norm(y, peak=0.8):
    return y / (np.max(np.abs(y)) or 1) * peak


def picture(ax, y, title):
    f, t, Z = stft(y, SR, nperseg=512, noverlap=448)
    S = 20 * np.log10(np.abs(Z) + 1e-9)
    ax.pcolormesh(t, f / 1000, S, vmin=S.max() - 60, vmax=S.max(), cmap="Greys", shading="auto")
    ax.set_ylim(1, 10); ax.set_title(title, fontsize=10, loc="left")
    ax.set_yticks([2, 4, 6, 8])
    for s in ax.spines.values():
        s.set_visible(False)


def main():
    os.makedirs(OUT, exist_ok=True)
    voices = {}
    for ch, spec in VOWELS.items():
        x, src = cut(spec)
        x = norm(x)
        cp = norm(copy_of(x))
        m = model_of(x)
        md = norm(sing(m, seed=ord(ch)))
        for name, y in (("original", x), ("copy", cp), ("model", md)):
            sf.write(os.path.join(OUT, f"{ch}-{name}.mp3"), y, SR, format="MP3")
        fig, axes = plt.subplots(1, 3, figsize=(12, 2.6), sharey=True)
        for ax, (name, y) in zip(axes, (("original", x), ("copy", cp), ("model", md))):
            picture(ax, y, name)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, f"{ch}.png"), dpi=80)
        plt.close(fig)
        voices[ch] = dict(model=m, source=src)
        print(f"{ch}: {src['species']:18s} {m['notes']:2d} notes every {1000 * m['period']:.0f} ms, "
              f"{1000 * m['note_dur']:.0f} ms long, around {m['pitch']:.0f} Hz, overtones {m['overtones']}")
    json.dump(voices, open(os.path.join(OUT, "voices.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
