"""A sound picture of one call, and a nearest-match comparison between two of them.

The picture is a log spectrogram from 1.5 to 8 kHz, ~2.9 ms per column, normalised so loudness
does not matter. Two calls are compared by sliding one along the other in time and keeping the
best correlation, with a penalty when their lengths differ.
"""
import numpy as np
from scipy.signal import stft

SR = 44100
NFFT, HOP = 512, 128
F_LO, F_HI = 1500, 8000


def picture(x, sr=SR, floor_db=45):
    f, t, Z = stft(x, sr, nperseg=NFFT, noverlap=NFFT - HOP, boundary=None, padded=False)
    band = (f >= F_LO) & (f <= F_HI)
    S = 20 * np.log10(np.abs(Z[band]) + 1e-9)
    S = np.maximum(S, S.max() - floor_db)
    return S


def active(S, margin_db=20):
    """Columns where the call is sounding (within margin of the loudest column)."""
    e = S.max(axis=0)
    on = np.where(e >= e.max() - margin_db)[0]
    return S[:, on[0]: on[-1] + 1] if len(on) else S


def _norm(S):
    S = S - S.mean()
    return S / (np.linalg.norm(S) + 1e-9)


def similarity(A, B, min_overlap=0.7):
    """Best normalised correlation over time shifts; 1 = identical shape."""
    if A.shape[1] < B.shape[1]:
        A, B = B, A  # A is the longer one
    la, lb = A.shape[1], B.shape[1]
    best = -1.0
    for lag in range(-(lb - 1), la):
        a0, a1 = max(0, lag), min(la, lag + lb)
        if a1 - a0 < min_overlap * lb:
            continue
        sa = A[:, a0:a1]
        sb = B[:, a0 - lag: a1 - lag]
        best = max(best, float(np.sum(_norm(sa) * _norm(sb))))
    return best * (lb / la) ** 0.5  # penalise length mismatch
