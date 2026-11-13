"""What happens to a sound between the speaker and the phone.

A simple, honest model, not a measurement: a small speaker (band limits, soft clipping), an
unknown tilt in the highs (speaker and phone colouring), a room (reverb whose share grows with
distance), level falling with distance against a fixed noise floor, and background noise.
Real recordings (test/recordings/) stay the reference; this model is for comparing options.
"""
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 44100


def speaker(x, sr=SR, lo=300, hi=9000, drive=1.5):
    """Small speaker: band-limited, slightly pushed."""
    sos = butter(2, [lo, hi], btype="band", fs=sr, output="sos")
    y = sosfilt(sos, x)
    peak = np.max(np.abs(y)) or 1.0
    return np.tanh(drive * y / peak) / np.tanh(drive)


def tilt(x, db_per_oct, sr=SR, pivot=3000):
    """Tilt the spectrum around a pivot frequency (dB per octave). Done in the frequency domain."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / sr)
    f[0] = 1.0
    gain_db = db_per_oct * np.log2(np.maximum(f, 50) / pivot)
    return np.fft.irfft(X * 10 ** (gain_db / 20), n)


def room_ir(rt60, distance, critical_distance, sr=SR, seed=0):
    """Impulse response: a direct sound plus an exponentially decaying diffuse tail.
    The direct-to-reverberant ratio falls 6 dB per doubling of distance past the critical
    distance, which is what makes a far phone hear more room than bird."""
    rng = np.random.default_rng(seed)
    n = int(sr * min(rt60 * 1.2, 2.5))
    t = np.arange(n) / sr
    tail = rng.standard_normal(n) * 10 ** (-3 * t / rt60)
    tail[: int(0.004 * sr)] = 0  # first reflections arrive a few ms after the direct sound
    tail /= np.sqrt(np.sum(tail ** 2))
    drr_db = 20 * np.log10(critical_distance / distance)
    ir = tail * 10 ** (-drr_db / 20)
    ir[0] += 1.0
    # high frequencies die faster in a real room: darken the tail a little
    sos = butter(1, 6000, btype="low", fs=sr, output="sos")
    ir[1:] = sosfilt(sos, ir[1:])
    return ir


def noise(n, kind, sr=SR, seed=0):
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    if kind == "hiss":
        return w
    if kind == "traffic":  # rumble: most energy below 500 Hz, some up to 2 kHz
        sos = butter(2, 500, btype="low", fs=sr, output="sos")
        return sosfilt(sos, w) + 0.15 * sosfilt(butter(2, [500, 2000], btype="band", fs=sr, output="sos"), w)
    if kind == "voices":  # babble: speech band, syllable-rate wobble
        sos = butter(2, [200, 3500], btype="band", fs=sr, output="sos")
        t = np.arange(n) / sr
        env = 0.35 + 0.65 * np.maximum(0, np.sin(2 * np.pi * 4.3 * t + 3 * np.sin(2 * np.pi * 0.7 * t)))
        return sosfilt(sos, w) * env
    raise ValueError(kind)


def rms(x):
    return np.sqrt(np.mean(x ** 2)) + 1e-12


def transmit(x, cond, sr=SR, seed=0):
    """Send x through the condition `cond` (a dict). Returns what the phone hears."""
    rng = np.random.default_rng(seed)
    y = speaker(x, sr) if cond.get("speaker", True) else x.copy()
    y = tilt(y, rng.uniform(-cond.get("tilt", 3), cond.get("tilt", 3)), sr)
    if cond.get("rt60"):
        ir = room_ir(cond["rt60"], cond["distance"], cond.get("critical", 1.0), sr, seed)
        y = fftconvolve(y, ir)[: len(y) + int(0.05 * sr)]
    # level falls with distance; noise floor stays fixed
    level = 1.0 / max(cond.get("distance", 0.3), 0.3)
    y = y / rms(y) * level
    for kind, snr_at_1m in cond.get("noise", []):
        nz = noise(len(y), kind, sr, seed + 7)
        nz = nz / rms(nz) * (1.0 * 10 ** (-snr_at_1m / 20))  # SNR given for a sound at 1 m
        y = y + nz
    return y
