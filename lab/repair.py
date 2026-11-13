"""Repair letters: Reed-Solomon over the bird alphabet (Claude web's first fallback idea, after OpenChirp).

The sender adds a few extra "repair" letters after the message; the listener uses them to fix letters
it heard wrong. Reed-Solomon fixes WRONG letters well (P repair letters fix P/2 wrong letters, or P
letters it knows are doubtful), but an EXTRA or MISSING letter shifts every letter after it. So the
listener also tries the decoded text with a letter removed or a gap added (up to two such edits), and
keeps the reading that the repair letters confirm with the fewest changes.

Field: GF(29), the 28 letters and one spare sound (only ever sung among the repair letters).
Spaces are not protected: they come from word pauses, which are rarely missed.
Messages longer than one block (28 letters with their repairs) are cut into blocks, interleaved
letter by letter so a burst of bad letters is shared between blocks.

Run:  .venv/bin/python lab/repair.py [repeats]   (sings and decodes with P = 0, 4, 6 in all rooms;
      lab/repair_eval.py then judges the repair on what the decoder heard)
"""
import itertools, os, sys
import numpy as np

Q = 29                     # field size (prime)
ALPHA = 2                  # a primitive element of GF(29)
SPARE = "#"                # the 29th sound


def inv(a):
    return pow(int(a), Q - 2, Q)


def poly_mul(a, b):        # coefficients lowest degree first
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                out[i + j] = (out[i + j] + x * y) % Q
    return out


def poly_eval(p, x):
    y = 0
    for c in reversed(p):
        y = (y * x + c) % Q
    return y


def generator(P):
    g = [1]
    for i in range(1, P + 1):
        g = poly_mul(g, [(-pow(ALPHA, i, Q)) % Q, 1])
    return g


def encode(msg, P):
    """msg: list of ints 0..28. Returns the P repair symbols (systematic code: codeword = msg + parity,
    msg[0] is the highest power)."""
    gh = list(reversed(generator(P)))    # highest first, gh[0] == 1
    d = list(msg) + [0] * P
    for i in range(len(msg)):
        f = d[i]
        if f:
            for j in range(1, P + 1):
                d[i + j] = (d[i + j] - f * gh[j]) % Q
    return [(-x) % Q for x in d[len(msg):]]


def syndromes(cw, P):
    """cw highest power first."""
    return [poly_eval(list(reversed(cw)), pow(ALPHA, j, Q)) for j in range(1, P + 1)]


def decode(cw, P, erasures=()):
    """Errors-and-erasures decoding (Sugiyama / Euclid, Forney). cw: list of ints, highest power first,
    erasures: positions in cw. Returns (corrected codeword, number of changed symbols) or None."""
    n = len(cw)
    S = syndromes(cw, P)
    if not any(S) and not erasures:
        return list(cw), 0
    e = len(erasures)
    if e > P:
        return None
    # position i (from the start) ↔ locator X = α^(n-1-i)
    X = lambda i: pow(ALPHA, n - 1 - i, Q)
    Gam = [1]
    for i in erasures:
        Gam = poly_mul(Gam, [1, (-X(i)) % Q])
    Sx = S[:]                               # S(x) = S1 + S2 x + …
    Xi = poly_mul(Sx, Gam)[:P]
    # extended Euclid on x^P and Xi(x) until deg(r) < (P + e) / 2
    r0, r1 = [0] * P + [1], Xi[:]
    t0, t1 = [0], [1]

    def deg(p):
        for k in range(len(p) - 1, -1, -1):
            if p[k]:
                return k
        return -1

    def sub(a, b):
        m = max(len(a), len(b))
        a, b = a + [0] * (m - len(a)), b + [0] * (m - len(b))
        return [(x - y) % Q for x, y in zip(a, b)]

    while deg(r1) >= (P + e) / 2:
        if deg(r1) < 0:
            break
        q = [0] * max(1, deg(r0) - deg(r1) + 1)
        r = r0[:]
        lead = inv(r1[deg(r1)])
        while deg(r) >= deg(r1):
            d = deg(r) - deg(r1)
            f = r[deg(r)] * lead % Q
            q[d] = (q[d] + f) % Q
            r = sub(r, [0] * d + [f * c % Q for c in r1])
        r0, r1 = r1, r
        t0, t1 = t1, sub(t0, poly_mul(q, t1))
    sigma, omega = t1, r1
    if deg(sigma) < 0 or sigma[0] == 0:
        return None
    k = inv(sigma[0])
    sigma = [c * k % Q for c in sigma]
    omega = [c * k % Q for c in omega]
    psi = poly_mul(sigma, Gam)
    dpsi = [(i * psi[i]) % Q for i in range(1, len(psi))]
    out = list(cw)
    changed = 0
    roots = 0
    for i in range(n):
        xinv = inv(X(i))
        if poly_eval(psi, xinv) == 0:
            roots += 1
            den = poly_eval(dpsi, xinv)
            if den == 0:
                return None
            val = (-poly_eval(omega, xinv) * inv(den)) % Q
            if val:
                out[i] = (out[i] - val) % Q
                changed += 1
    if roots != deg(psi):
        return None
    if any(syndromes(out, P)):
        return None
    return out, changed


# ---------- the message layout: blocks, interleaved ----------

def layout(L, P):
    """L message letters → number of blocks and each block's message length."""
    B = max(1, -(-L // (Q - 1 - P)))
    base, extra = divmod(L, B)
    return B, [base + (1 if b < extra else 0) for b in range(B)]


def protect(letters, P, symbols):
    """letters: str of message letters (no spaces). Returns the repair letters to sing after them."""
    if P == 0:
        return ""
    idx = {c: i for i, c in enumerate(symbols)}
    L = len(letters)
    B, ks = layout(L, P)
    blocks = [[idx[letters[i]] for i in range(b, L, B)] for b in range(B)]
    assert [len(x) for x in blocks] == ks
    par = [encode(m, P) for m in blocks]
    return "".join(symbols[par[b][j]] for j in range(P) for b in range(B))


def check(stream, P, symbols, erasures=()):
    """stream: message letters + repair letters as heard (ints). Returns corrected message ints and the
    number of letters changed, or None."""
    N = len(stream)
    # find L with L + B·P == N
    for L in range(1, N):
        B, ks = layout(L, P)
        if L + B * P == N:
            break
    else:
        return None
    msg, par = stream[:L], stream[L:]
    out = [None] * L
    full = list(stream)
    total = 0
    for b in range(B):
        mpos = list(range(b, L, B))
        ppos = [L + j * B + b for j in range(P)]
        cw = [stream[i] for i in mpos + ppos]
        er = [k for k, i in enumerate(mpos + ppos) if i in erasures]
        r = decode(cw, P, er)
        if r is None:
            return None
        cw2, ch = r
        total += ch
        for k, i in enumerate(mpos + ppos):
            full[i] = cw2[k]
        for k, i in enumerate(mpos):
            out[i] = cw2[k]
    check.full = full
    return out, total


def repair(text, P, symbols, max_edits=2, edit_cost=1.5):
    """text: the decoder's output (letters, spaces, repair letters at the end).
    Returns (repaired text without repair letters, cost) or (None, None) when nothing checks out."""
    if P == 0:
        return text, 0
    idx = {c: i for i, c in enumerate(symbols)}
    letters = [c for c in text if c != " "]
    # where the spaces were: after how many letters
    spaces, n = [], 0
    for c in text:
        if c == " ":
            spaces.append(n)
        else:
            n += 1
    s = [idx[c] for c in letters if c in idx]
    best = (None, 1e9, None)
    N = len(s)
    for k in range(max_edits + 1):
        if k * edit_cost >= best[1]:
            break
        # each edit: ("del", i) removes letter i, ("gap", i) adds an unknown letter before i
        edits = [("del", i) for i in range(N)] + [("gap", i) for i in range(N + 1)]
        for combo in itertools.combinations(edits, k):
            cur, er, ok = list(s), [], True
            # apply from the end so positions stay valid
            for kind, i in sorted(combo, key=lambda z: -z[1]):
                if kind == "del":
                    del cur[i]
                else:
                    cur.insert(i, 0)
            # erasure positions after all edits
            shift = 0
            pos = []
            for kind, i in sorted(combo, key=lambda z: z[1]):
                if kind == "del":
                    shift -= 1
                else:
                    pos.append(i + shift)
                    shift += 1
            r = check(cur, P, symbols, set(pos))
            if r is None:
                continue
            msg, ch = r
            cost = k * edit_cost + ch
            if cost < best[1]:
                best = (msg, cost, combo)
    msg, cost, combo = best
    if msg is None:
        return None, None
    # put the spaces back, roughly where they were (shifted by the edits before them)
    def moved(n):
        d = 0
        for kind, i in combo:
            if i < n:
                d += -1 if kind == "del" else 1
        return n + d
    sp = sorted({moved(n) for n in spaces if 0 < moved(n) < len(msg)})
    out, j = "", 0
    for i, v in enumerate(msg):
        if j < len(sp) and sp[j] == i:
            out += " "
            j += 1
        out += symbols[v]
    return out, cost


# ---------- the test in rooms ----------

def collect(repeats=1, Ps=(0, 4, 6)):
    """Sing, send through every room and decode; keep what the decoder said (with its doubts)."""
    import os, pickle
    from multiprocessing import Pool
    from decode import SENTENCES, CONDITIONS
    jobs = [(P, cname, r, si) for P in Ps for cname in CONDITIONS for r in range(repeats) for si in range(len(SENTENCES))]
    with Pool(max(1, os.cpu_count() - 1)) as pool:
        res = pool.map(run_one, jobs)
    out = [dict(P=P, room=cname, rep=r, sentence=si, **d) for (P, cname, r, si), d in zip(jobs, res)]
    pickle.dump(out, open(os.path.join(os.path.dirname(__file__), "out", "repair-decodes.pkl"), "wb"))
    return out


_V = None


def voice():
    global _V
    if _V is None:
        import os, json, sys
        sys.path.insert(0, os.path.dirname(__file__))
        from decode import load_voice, Decoder
        from choose_consonants import synth_note
        from sketch import cut
        v, snd, sr = load_voice()
        spare = json.load(open(os.path.join(os.path.dirname(__file__), "out", "spare.json")))
        x, _ = cut(tuple(spare["spec"][1:]) if spare["spec"][0] == "cut" else spare["spec"][1])
        snd[SPARE] = synth_note(x)
        v["letters"][SPARE] = dict(file=None, vowel=False, dur=len(snd[SPARE]) / sr)
        symbols = [c for c in v["letters"] if c != SPARE] + [SPARE]
        _V = (v, snd, sr, Decoder(v, snd, sr), symbols)
    return _V


def run_one(job):
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from decode import SENTENCES, CONDITIONS, sing, heard, normalize
    P, cname, r, si = job
    v, snd, sr, dec, symbols = voice()
    text = SENTENCES[si]
    words = [w for w in ("".join(c for c in w if c in v["letters"] and c != SPARE) for w in normalize(text).split()) if w]
    clean = " ".join(words)
    rep = protect("".join(words), P, symbols)
    sent = clean + (" " + rep if rep else "")
    y, sung = sing(sent, v, snd, seed=10 * r + si)
    h = heard(y, CONDITIONS[cname], sr, seed=100 * r + si)
    got, info = dec.decode(h, 48000)
    return dict(clean=clean, sung=sung, got=got, letters=info.get("letters", []), dur=len(y) / sr)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    collect(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
