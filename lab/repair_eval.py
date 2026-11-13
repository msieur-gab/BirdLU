"""Judge the repair letters on what the decoder actually heard (lab/out/repair-decodes.pkl, made by
lab/repair.py), hard and soft.

hard   the decoded text only: try removing or adding up to two letters, keep what the repair letters
       confirm with the fewest changes.
soft   the decoder also says how sure it is of each letter (its fit and how far ahead of the next best
       letter it was). Doubtful letters are handed to Reed-Solomon as "unknown" (an unknown letter costs
       half a wrong one), changing a sure letter is expensive, removing a weak letter is cheap. The
       cheapest reading that the repair letters confirm wins; if even that is too expensive, the
       listener says it is unsure instead of showing a wrong message.

Run:  .venv/bin/python lab/repair_eval.py
"""
import itertools, os, pickle, sys
from multiprocessing import Pool
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repair import check, repair, Q, SPARE

SYMBOLS = list("eaoiuéyètnsrldcmphvgfbqjwkxz") + [SPARE]
IDX = {c: i for i, c in enumerate(SYMBOLS)}


def clip01(x):
    return max(0.0, min(1.0, x))


def sureness(L):
    """0 (doubtful) … 1 (sure), from the decoder's fit margin and placement score."""
    return 0.5 * clip01(L["margin"] / 0.4) + 0.5 * clip01(L["score"] / 8.0)


def soft_repair(letters, P, max_edits=2, change_base=0.3, gap_cost=1.0, del_base=0.5, erase_steps=(0, 2, 4, 6, 8)):
    """letters: the decoder's letters (dicts with ch, score, margin), message then repair letters.
    Returns (message text without spaces, cost, second best cost) or (None, inf, inf)."""
    s = [IDX[x["ch"]] for x in letters]
    sure = [sureness(x) for x in letters]
    N = len(s)
    del_cost = []
    for i, x in enumerate(letters):
        c = del_base + clip01(x["score"] / 8.0)
        if i > 0 and letters[i - 1]["ch"] == x["ch"]:
            c *= 0.5          # a letter right after the same letter: often an echo
        del_cost.append(c)
    best, second = (None, np.inf), np.inf
    edits = [("del", i) for i in range(N)] + [("gap", i) for i in range(N + 1)]
    for k in range(max_edits + 1):
        for combo in itertools.combinations(edits, k):
            if any(a[1] == b[1] for a, b in itertools.combinations(combo, 2)):
                continue
            ecost = sum(del_cost[i] if kind == "del" else gap_cost for kind, i in combo)
            if ecost >= second:
                continue
            # build the edited stream; keep where each symbol came from (-1: a gap)
            src = list(range(N))
            for kind, i in sorted(combo, key=lambda z: -z[1]):
                if kind == "del":
                    del src[i]
                else:
                    src.insert(i, -1)
            cur = [s[j] if j >= 0 else 0 for j in src]
            gaps = [p for p, j in enumerate(src) if j < 0]
            order = sorted((p for p, j in enumerate(src) if j >= 0), key=lambda p: sure[src[p]])
            seen = set()
            for ne in erase_steps:
                er = tuple(sorted(gaps + order[:ne]))
                if er in seen or len(er) > len(cur):
                    continue
                seen.add(er)
                r = check(cur, P, SYMBOLS, set(er))
                if r is None:
                    continue
                msg, _ = r
                full = check.full
                cost = ecost
                for p, j in enumerate(src):
                    if j >= 0 and full[p] != s[j]:
                        cost += change_base + sure[j]
                key = tuple(msg)
                if cost < best[1]:
                    if best[0] is not None and tuple(best[0]) != key:
                        second = min(second, best[1])
                    best = (msg, cost)
                elif tuple(best[0]) != key:
                    second = min(second, cost)
    msg, cost = best
    if msg is None:
        return None, np.inf, np.inf
    return "".join(SYMBOLS[v] for v in msg), cost, second


def judge(r):
    clean = r["clean"].replace(" ", "")
    got = r["got"].replace(" ", "")
    raw_ok = got == (r["sung"].replace(" ", ""))
    if r["P"] == 0:
        return dict(raw_ok=raw_ok, hard=raw_ok, soft=(got if raw_ok else None, 0.0, np.inf), clean=clean)
    h, _ = repair(r["got"], r["P"], SYMBOLS)
    hard = h is not None and h.replace(" ", "") == clean
    hard_flag = h is None
    soft = soft_repair(r["letters"], r["P"]) if r["letters"] else (None, np.inf, np.inf)
    return dict(raw_ok=raw_ok, hard=hard, hard_flag=hard_flag, soft=soft, clean=clean)


def main():
    D = pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "repair-decodes.pkl"), "rb"))
    with Pool(max(1, os.cpu_count() - 1)) as pool:
        J = pool.map(judge, D)
    pickle.dump(J, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "repair-judged.pkl"), "wb"))
    report(D, J)


def report(D, J, limits=(2.0, 3.0, 4.0, np.inf)):
    rooms = list(dict.fromkeys(r["room"] for r in D))
    groups = {"simulated rooms": [r for r in rooms if not r.startswith("real")],
              "your living room": [r for r in rooms if r.startswith("real")]}
    Ps = sorted({r["P"] for r in D})
    for gname, rs in groups.items():
        print(f"\n== {gname} ==")
        for P in Ps:
            sel = [(r, j) for r, j in zip(D, J) if r["P"] == P and r["room"] in rs]
            n = len(sel)
            dur = np.mean([r["dur"] for r, _ in sel])
            if P == 0:
                print(f"P=0  ({dur:.1f} s)  right {sum(j['raw_ok'] for _, j in sel)}/{n}, every other one silently wrong")
                continue
            raw = sum(j["raw_ok"] for _, j in sel)
            hard = sum(j["hard"] for _, j in sel)
            hflag = sum(j["hard_flag"] for _, j in sel)
            print(f"P={P}  ({dur:.1f} s)  heard right {raw}/{n} · hard repair: right {hard}, flagged {hflag}, wrong {n - hard - hflag}")
            for lim in limits:
                ok = wrong = flag = 0
                for _, j in sel:
                    msg, cost, sec = j["soft"]
                    if msg is None or cost > lim:
                        flag += 1
                    elif msg == j["clean"]:
                        ok += 1
                    else:
                        wrong += 1
                print(f"      soft repair, unsure above cost {lim}: right {ok}, flagged unsure {flag}, wrong {wrong}")


if __name__ == "__main__":
    main()
