"""The conflict check for letters drawn on draw.html (MUSICOLOGY.md, step 17).

Takes the file exported by the page ("Export my letters"), sings the drawn letters with lab/synth.py `sing` (the
same steps as js/synth.js), and makes a test voice: version D with those letters replaced
(birds/voices/<name>/, listed in birds/voices/index.json, so Send and Listen can use ?voice=<name> for a real test).
Then, for D and for the new voice (lab/confusions.py, lab/likeness.py):
  - the letter pairs the decoder finds most alike through a simulated echo, and every pair that holds a drawn letter
    and is above 0.65;
  - every Send preset sung and decoded, clean and through simulated rooms.
A guide only: simulated rooms are not evidence, real recordings and Gab's ear decide.
Run:  .venv/bin/python lab/draw_check.py ~/Downloads/bird-drawn-letters.json [name, default "drawn"]
"""
import json, os, re, shutil, sys
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, ROOT
from likeness import likeness, room
from synth import sing, trim
from variants import level
import confusions

BASE = "nightingale-d"
VOICES = os.path.join(ROOT, "birds", "voices")


def main(path, name="drawn"):
    assert re.fullmatch(r"[a-z0-9-]{1,30}", name) and name != BASE, "name: small letters, digits, hyphens"
    drawn = json.load(open(os.path.expanduser(path)))["letters"]
    if not drawn:
        sys.exit("No drawn letter in that file.")
    out = os.path.join(VOICES, name)
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(os.path.join(VOICES, BASE), out)
    v = json.load(open(os.path.join(out, "voice.json")))
    sr = v["sample_rate"]
    for ch, m in sorted(drawn.items()):
        y = level(trim(sing(m, seed=m.get("seed", ord(ch)))))
        if ch not in v["letters"]:       # a sound the base voice does not have yet (the accent call "*")
            v["letters"][ch] = dict(file=f"sign-{ord(ch):x}.wav", vowel=False, sign=True)
        sf.write(os.path.join(out, v["letters"][ch]["file"]), y, sr, subtype="PCM_16")
        v["letters"][ch].update(dur=round(len(y) / sr, 4), gesture="drawn by Gab")
        print(f"{ch}: {m['notes']} note(s) of {1000 * m['note_dur']:.0f} ms around {m['pitch']:.0f} Hz, {1000 * len(y) / sr:.0f} ms in all")
    letters = "".join(sorted(drawn))
    v["note"] = f"Test voice {name}: version D with the letters {letters} drawn by Gab on draw.html. Made by lab/draw_check.py."
    json.dump(v, open(os.path.join(out, "voice.json"), "w"), ensure_ascii=False, indent=1)
    ip = os.path.join(VOICES, "index.json")
    index = [e for e in json.load(open(ip)) if e["name"] != name]
    index.append(dict(name=name, about=f"Version D with the letters {letters} drawn by Gab (draw.html)."))
    json.dump(index, open(ip, "w"), ensure_ascii=False, indent=1)

    L = {}
    for n in (BASE, name):
        vv, snd, sr = load_voice(os.path.join(VOICES, n))
        L[n] = likeness(snd, sr, [c for c in vv["letters"] if not vv["letters"][c].get("accent")], room(sr, 1.0))   # letters and signs
    print(f"\nPairs with a drawn letter, as alike to the decoder through a 1 s echo (above 0.65 is close; D's value in brackets):")
    rows = sorted((p for p in L[name] if p[0] in drawn or p[1] in drawn), key=L[name].get, reverse=True)
    for a, b in rows[:12]:
        flag = "  CLOSE" if L[name][(a, b)] > 0.65 else ""
        print(f"   {a}/{b}  {L[name][(a, b)]:.2f}  ({L[BASE][(a, b)]:.2f}){flag}")
    confusions.main([BASE, name])
    print(f"\nTo hear and test it for real: send-bird.html?voice={name} and listen-bird.html?voice={name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(*sys.argv[1:3])
