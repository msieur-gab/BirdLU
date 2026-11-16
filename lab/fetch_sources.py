"""Download the source bird recordings from Wikimedia Commons (mirrors of xeno-canto, CC BY-SA 4.0).

Writes lab/sources/<XC id>.mp3 and lab/sources/sources.json (species, recordist, licence, links).
lab/sources/ is not in git: only cut clips and their credits are. Polite: one file at a time,
a pause between files, and back-off when the server asks to slow down.

Run:  .venv/bin/python lab/fetch_sources.py
"""
import json, os, re, time, urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "lab", "sources")
UA = {"User-Agent": "BirdLU-research/0.1 (non-commercial prototype)"}
TITLES = [
    "Troglodytes troglodytes - Eurasian Wren XC461185.mp3", "Troglodytes troglodytes - Eurasian Wren XC543697.mp3",
    "Fringilla coelebs - Common Chaffinch XC489896.mp3", "Fringilla coelebs - Common Chaffinch XC538310.mp3",
    "Turdus merula - Common Blackbird XC446151.mp3", "Turdus merula - Common Blackbird XC533763.mp3",
    "Phylloscopus collybita - Common Chiffchaff XC170664.mp3", "Phylloscopus collybita - Common Chiffchaff XC478019.mp3",
    "Sitta europaea - Eurasian Nuthatch XC433160.mp3", "Sitta europaea - Eurasian Nuthatch XC466459.mp3",
    "Turdus philomelos - Song Thrush XC541754.mp3", "Turdus philomelos - Song Thrush XC503633.mp3",
    "Chloris chloris - European Greenfinch XC482886.mp3", "Chloris chloris - European Greenfinch XC183761.mp3",
    "Emberiza citrinella - Yellowhammer XC531169.mp3", "Emberiza citrinella - Yellowhammer XC481630.mp3",
    # 16 Nov: the nightingale, for the opening and closing (Gab: "the Chinese bird ... for the emperors? Rossignol?")
    "Luscinia megarhynchos - Common Nightingale XC138451.mp3", "Luscinia megarhynchos - Common Nightingale XC473316.mp3",
    "Luscinia megarhynchos - Common Nightingale XC546043.mp3",
]


def get(url, tries=6):
    wait = 10
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            ra = e.headers.get("Retry-After")
            time.sleep(int(ra) if ra and ra.isdigit() else wait)
            wait *= 2
    raise RuntimeError("gave up on " + url)


def main():
    os.makedirs(DIR, exist_ok=True)
    meta = []
    for i in range(0, len(TITLES), 8):
        q = "|".join("File:" + t for t in TITLES[i:i + 8])
        url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(
            dict(action="query", format="json", prop="imageinfo", iiprop="url|extmetadata", titles=q))
        for p in json.loads(get(url))["query"]["pages"].values():
            ii, m = p["imageinfo"][0], p["imageinfo"][0]["extmetadata"]
            sci, rest = p["title"][5:].split(" - ", 1)
            common, xc = rest.rsplit(" ", 1)
            xc = xc.split(".")[0]
            meta.append(dict(
                id=xc, file=f"{xc}.mp3", scientific=sci, species=common,
                recordist=re.sub("<[^>]+>", "", m.get("Artist", {}).get("value", "")).strip(),
                licence=m.get("LicenseShortName", {}).get("value", ""),
                licence_url=m.get("LicenseUrl", {}).get("value", ""),
                commons=ii["descriptionurl"], xeno_canto=f"https://xeno-canto.org/{xc[2:]}", url=ii["url"]))
    meta.sort(key=lambda r: (r["species"], r["id"]))
    json.dump(meta, open(os.path.join(DIR, "sources.json"), "w"), ensure_ascii=False, indent=1)
    for r in meta:
        path = os.path.join(DIR, r["file"])
        if not os.path.exists(path):
            data = get(r["url"])
            open(path, "wb").write(data)
            time.sleep(4)
        print(f'{r["id"]:9s} {r["species"]:20s} {os.path.getsize(path) / 1e6:4.1f} MB  {r["licence"]}  {r["recordist"]}', flush=True)


if __name__ == "__main__":
    main()
