"""Write birds/alphabets.json: three candidate bird alphabets to compare by ear.

Each letter is one bird syllable, sung once or twice ("doubled": the same syllable repeated
quickly, as birds do). 17 sturdy shapes are used: the 16 core syllables with B04 left out (a room
turns it into B03, see lab/distinct.py), plus the reserves R01 and R03. Space is a pause.
Strength order comes from step 1 (median margin in the room conditions).

  A  vowels from the robin, consonants from the blue and great tits
  B  vowels from the great tit, consonants from the blue tit and the robin
  C  no species rule: the sturdiest syllables go to the most frequent letters
  D  "a message coming from the forest" (Gab): A's letters, each sung as a trill, every species
     from its own place. Not checked by lab/check_alphabets.py yet (its timing is loose on purpose).

The page (bird-alphabets.html) and the check (lab/check_alphabets.py) both read this file,
timings included, so they always build the same message.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# most frequent first, English and French mixed
FREQ = list("easitnroulcdmpéhvgfbyqwjkxzè")

# sturdiest first (step 1); B05 is long (0.34 s) so it is kept for a rarer letter
STRENGTH = ["B13", "B16", "B11", "B15", "B12", "B02", "B08", "B06", "B09", "R03", "R01",
            "B14", "B10", "B03", "B07", "B01", "B05"]

TIMING = {
    "slow":   {"letter_gap": 0.20, "double_gap": 0.045, "word_gap": 0.60},
    "lively": {"letter_gap": 0.09, "double_gap": 0.030, "word_gap": 0.32},
}


def one(s): return [s]
def two(s): return [s, s]


A = {
    "name": "A · robin vowels, tit consonants",
    "idea": "Vowels sound like a robin, consonants like the tits. A misheard vowel still sounds like a vowel. i is the robin's high note, o its low round one.",
    "letters": {
        "e": one("B12"), "a": one("B11"), "i": one("B16"), "o": one("B13"), "u": one("B14"),
        "é": one("B15"), "y": two("B16"), "è": two("B15"),
        "s": one("B02"), "t": one("B08"), "n": one("B06"), "r": one("B09"), "l": one("R03"),
        "d": one("R01"), "c": one("B10"), "m": one("B03"), "p": one("B07"), "h": one("B01"),
        "v": one("B05"),
        "g": two("B02"), "f": two("B06"), "b": two("B10"), "q": two("B03"), "w": two("B07"),
        "j": two("B01"), "k": two("R03"), "x": two("B09"), "z": two("R01"),
    },
}

B = {
    "name": "B · great-tit vowels, blue-tit and robin consonants",
    "idea": "The reverse family split: vowels are the great tit's notes, consonants come from the blue tit and the robin.",
    "letters": {
        "e": one("B09"), "a": one("B08"), "i": one("R03"), "o": one("R01"), "u": one("B10"),
        "é": two("B09"), "y": two("R03"), "è": two("B08"),
        "s": one("B15"), "t": one("B16"), "n": one("B11"), "r": one("B12"), "l": one("B02"),
        "d": one("B13"), "c": one("B14"), "m": one("B06"), "p": one("B03"), "h": one("B07"),
        "v": one("B01"), "g": one("B05"),
        "f": two("B16"), "b": two("B15"), "q": two("B02"), "w": two("B14"), "j": two("B11"),
        "k": two("B06"), "x": two("B12"), "z": two("B03"),
    },
}


def frequency_alphabet():
    letters = {}
    singles = FREQ[:len(STRENGTH)]
    for ch, s in zip(singles, STRENGTH):
        letters[ch] = one(s)
    # rarer letters: doubled, using the short sturdy syllables first (doubling a long one is slow)
    short_first = ["B16", "B02", "B14", "B15", "B06", "B10", "R03", "B12", "R01", "B09", "B11"]
    for ch, s in zip(FREQ[len(STRENGTH):], short_first):
        letters[ch] = two(s)
    return letters


C = {
    "name": "C · sturdiest syllables for the most used letters",
    "idea": "No species rule, a mixed chorus. The syllables that best survive a room carry e, a, s, i, t…; rare letters are sung twice.",
    "letters": frequency_alphabet(),
}


D = {
    "name": "D · a forest of trills",
    "idea": "Each letter is a little trill: one bird repeats its syllable a few times, fast for common letters, slower for rare ones. Each species sings from its own place, near or far, left or right. Same letters as A.",
    "style": "forest",
    "letters": A["letters"],
    # where each bird sits: level, how much forest echo, left (-1) to right (+1)
    "voices": {
        "European Robin":    {"gain": 1.0, "wet": 0.25, "pan": -0.45},
        "Eurasian Blue Tit": {"gain": 0.8, "wet": 0.45, "pan": 0.5},
        "Great Tit":         {"gain": 0.6, "wet": 0.7,  "pan": 0.1},
    },
    # a trill aims at about `target` seconds; single letters trill fast, "doubled" letters slowly
    "trill": {"target": 0.38, "fast_gap": 0.03, "slow_gap": 0.11},
    "gaps": {"letter": [0.12, 0.26], "word": [0.5, 0.75]},
}


def main():
    for v in (A, B, C, D):
        assert set(v["letters"]) == set(FREQ), (v["name"], set(FREQ) ^ set(v["letters"]))
        used = [tuple(x) for x in v["letters"].values()]
        assert len(used) == len(set(used)), v["name"] + ": two letters share a call"
    out = {
        "note": "Generated by lab/make_alphabets.py. Each letter: the syllables sung, in order.",
        "timing": TIMING,
        "fade_ms": 4,
        "versions": {"A": A, "B": B, "C": C, "D": D},
    }
    path = os.path.join(ROOT, "birds", "alphabets.json")
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)
    print("wrote", path)


if __name__ == "__main__":
    main()
