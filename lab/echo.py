"""The opening as a tuning fork, and the echo taken away.

The listener knows exactly how the opening call sounds when clean. Between its notes, and in the
short silence after it, the clean call is silent: whatever the phone hears there is the room's echo.
How fast that echo fades gives the room's reverberation time (RT60: the time for sound to fade by
60 dB).

With it, the late echo is taken out of the sound picture before letters are read (Lebart et al. 2001,
https://www.ee.columbia.edu/~dpwe/papers/LebBD01-ssdereverv.pdf): the echo heard now is predicted
from what was heard 50 ms ago, faded at the room's rate, and subtracted. A trill's tail no longer
covers the short note after it ("overlap-masking"), and no longer fills a word pause.

Written to be ported line by line to JavaScript.
"""
import numpy as np

HOP_S = 0.005


def opening_reference(db_clean, level_clean):
    """From the clean opening's picture: which frames are loud, trimmed as the template is."""
    on = level_clean > level_clean.max() - 30
    a, b = np.where(on)[0][[0, -1]]
    lev = level_clean[a:b + 1]
    return dict(db=db_clean[:, a:b + 1], loud=lev > lev.max() - 30)


def estimate_rt60(db, start, ref, after_s=0.15, noise_pct=10):
    """db: heard picture (bands × frames), start: frame where the opening template begins.
    In every silence of the clean call (between its notes, and just after it), in the bands where the
    call is strong, the heard level should fall in a straight line (in dB): its slope is the room's.
    Returns the reverberation time in seconds (None if it cannot be measured)."""
    n = ref["loud"].size
    after = int(after_s / HOP_S)
    loud = np.concatenate([ref["loud"], np.zeros(after, bool)])
    floor = np.percentile(db, noise_pct, axis=1)
    top = ref["db"].max(axis=1)
    bands = np.where(top > top.max() - 15)[0]
    num = den = 0.0
    count = 0
    last = None
    seg = []                               # frames of the current silence: (tau, k)
    def close(seg):
        nonlocal num, den, count
        if len(seg) < 4:
            return
        for bnd in bands:
            pts = [(tau, db[bnd, start + k]) for tau, k in seg if db[bnd, start + k] > floor[bnd] + 6]
            if len(pts) < 4:
                continue
            t = np.array([p[0] for p in pts]) * HOP_S
            h = np.array([p[1] for p in pts])
            tc, hc = t - t.mean(), h - h.mean()
            num += float(np.sum(tc * hc))
            den += float(np.sum(tc * tc))
            count += len(pts)
    for k in range(min(loud.size, db.shape[1] - start)):
        if loud[k]:
            close(seg)
            seg = []
            last = k
            continue
        if last is None:
            continue
        tau = k - last
        # the tail 20 to 120 ms after a note (the first drop, when the direct sound stops, says how
        # near the speaker is, not how long the room rings)
        if 4 <= tau <= 24:
            seg.append((tau, k))
    close(seg)
    if count < 20 or den == 0:
        return None
    slope = num / den                      # dB per second
    if slope >= -1:
        return 2.5
    return float(np.clip(-60.0 / slope, 0.1, 2.5))


def dereverb(db, rt60, delay_s=0.05, floor_db=15.0):
    """Take the late echo out of a picture (dB, bands × frames). Also returns, per frame, how much of
    what is heard is new sound rather than echo (1: all new, 0: all echo)."""
    P = 10 ** (db / 10)
    d = int(round(delay_s / HOP_S))
    delta = 3 * np.log(10) / rt60
    R = np.zeros_like(P)
    R[:, d:] = P[:, :-d] * np.exp(-2 * delta * delay_s)
    G = np.clip(1 - R / (P + 1e-20), 0, 1)
    direct = (P * G).sum(axis=0) / (P.sum(axis=0) + 1e-20)
    G = np.maximum(G, 10 ** (-floor_db / 10))
    return 10 * np.log10(P * G + 1e-12), direct
