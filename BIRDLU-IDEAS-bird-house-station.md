# BirdLU ideas: the bird house station

For Claude Code, working in `msieur-gab/BirdLU`.
Read `BIRD-VOICE.md` (branch `echo-tuning`) and `BIRDLU-IDEAS-accents-and-model.md` first. The station sings the same bird voice.

## The aim

A small battery station that keeps about 10 letters and sings them one at a time, in random order, with pauses. People listen with the phone page (`listen-bird.html`) to pick up a letter. They can also leave a new one. A small e-paper screen shows a bird, or a QR code while the station is open for new letters.

## Working rules

1. **Gab's ear decides** anything people hear (volume, pauses, speaker, enclosure sound).
2. **Real tests decide.** Every step is checked with a phone listening in a real place.
3. **Low power before features.** The station sleeps whenever it isn't singing.
4. **Stop and check with Gab** at each "Done when" before starting the next step.

## Prototype hardware

| Part | Why |
|---|---|
| **Waveshare ESP32-S3-ePaper-1.54**, black and white, with battery | ESP32-S3, 8 MB flash and 8 MB PSRAM, 200 × 200 e-paper, ES8311 audio codec, speaker header, lithium battery header with charging, RTC, button. Choose black and white: about 2 s full refresh, against 20 s for the colour version. |
| **MAX98357A I2S amplifier breakout** (Adafruit, from BerryBase) | Backup audio path. It needs no setup over I2C and no master clock, so it works with MicroPython out of the box. It also drives a speaker harder (3 W class D). It connects to the board's 2 × 6 expansion header if 3 free GPIOs are there. Check the pinout image and schematic on the Waveshare docs before wiring. |
| **Speaker, 3 W, 4 Ω, about 40 mm** | The onboard speaker is small. Bird notes sit at 2–9 kHz, so a small full-range speaker is enough. |
| **Larger LiPo with an MX1.25 plug** | The included battery's capacity isn't stated. **Check the plug's polarity before connecting**: MX1.25 plugs from other sellers are often wired the other way round. |

## How the station sings

- **No MP3, no recorded letters.** The station keeps letters as **text** and sings them by stringing together one short sound per letter, exactly as `send-bird.html` / `js/birdsong.js` does today.
- **The voice on the station:** each sound in `birds/voice/` (39 sounds, 5.8 s in total, about 584 KB) is exported as **raw PCM, 16-bit, mono, 44.1 kHz**, plus a small JSON file with the voice's timing (`gap_in_word`, `gap_jitter`, `word_gap`, the closing pattern). That's about 7 % of the flash.
  - Add an export step next to `lab/export_voice.py`.
  - When the accent calls and the doubled-letter rule from the ideas file are chosen, they are exported the same way.
- **No decoding on the station.** Samples are copied from flash to I2S.
- **Play at the voice's own rate (44.1 kHz).** Never resample on the station: the "metallic" sound on 13 Nov came from a rate mismatch.
- **The same text sung by the laptop and by the station must sound the same and decode the same.**

## Software

- **MicroPython first** (`machine.I2S`), with **Arduino / ESP-IDF as the fallback** (Waveshare supports only those officially).
- **Two MicroPython unknowns, both checked in step 0:**
  - **ES8311 setup:** the codec is set up through a list of register writes over I2C. Port it from Espressif's `esp_codec_dev` / ES8311 C driver.
  - **Master clock:** the ES8311 usually wants a master clock, and MicroPython's I2S class has not supported one on ESP32. Check whether the codec can take its clock from the I2S bit clock instead. If not, use the MAX98357A, or move to Arduino.
- **Parts of the program:** audio out, the e-paper driver, a letter store (JSON in flash), a scheduler with deep sleep and RTC wake-up, the button, and a short Wi-Fi window for leaving letters.

---

## Step 0: "hello bird"

**Goal:** prove the audio path and choose MicroPython or Arduino.

**Work:** flash MicroPython, set up the ES8311 and play one bird sound from flash through the speaker. Try the MAX98357A path as well.

**Done when**
- One sound plays cleanly through at least one path.
- Gab has heard it.
- The choice (MicroPython or Arduino, ES8311 or MAX98357A) is written down with the reason.
- If MicroPython blocks for more than an afternoon, switch and note why.

## Step 1: sing a letter

**Goal:** the station turns text into song by itself.

**Work:** string the sounds together on the station using the voice timing, and sing the benchmark sentences (`test/benchmark.txt` from the ideas file).

**Done when**
- `listen-bird.html` on a phone decodes the station's song as well as the laptop's song for the same sentences, at 30 cm and 2–3 m.
- Recordings are kept in `test/recordings-station/`.

## Step 2: loud enough, and still a bird

**Goal:** the right audio path and speaker for a real place.

**Work:** compare the onboard ES8311 path and the MAX98357A, each with the 40 mm speaker, at 2–3 m and 6–7 m, at several volumes.

**Done when**
- There is a table of decoding results per path, distance and volume.
- Gab has chosen the path, speaker and volume by ear: loud enough to read, still sounding like a bird.

## Step 3: the station loop

**Goal:** the station lives on its own.

**Work**
- Keep up to 10 letters in flash.
- Wake on the RTC, sing one letter chosen at random, and go back to deep sleep.
- The pause between letters is a setting (for example every 2, 5 or 10 minutes).
- The e-paper screen shows the bird while the station sleeps. E-paper keeps its image with no power.

**Done when**
- The station runs for 24 hours on battery with no crash.
- It sings every letter over time.
- The screen stays right.

## Step 4: leaving a letter

**Goal:** a passer-by can leave a new letter without installing anything.

**Work**
- **Button press:** Wi-Fi opens for about 2 minutes as a small open access point with a captive portal.
- **Screen:** shows a QR code to join, then the page address.
- **The page:** a single text field with a character limit, where the person writes a letter.
- **On send:** the station stores the text and replaces the oldest letter.
- **Wi-Fi closes** after the window or after a letter is received.

**Done when**
- A phone can join through the QR code and leave a letter.
- The station sings it in the next cycle, and a second phone decodes it.

**Gab decides before this is used in a public place:**
- how letters are moderated;
- the maximum length;
- whether letters expire.

## Step 5: power

**Goal:** know how long a station lasts on one charge.

**Work:** measure one full cycle (wake, sing, sleep) and one Wi-Fi window with a USB power meter or a current meter.

**Done when** there is a table of days per charge for:
- 2 or 3 pause settings;
- 2 volumes;
- 0, 5 and 20 letters left per day.

Gab then sets the target.

---

## Open questions

- **The house itself:** the enclosure as a wooden bird house, with an opening for the sound and a window for the screen. Gab designs it. Test whether wood colours the sound or affects decoding.
- **Quiet hours:** should the station rest at night, and sing more at dawn, like real birds?
- **Outdoors:** weather, cold (LiPo batteries dislike frost), theft.
- **Station to station:** letters carried by people only (the plan today), or stations that also sing to each other?

## What to deliver at each step

- Code on its own branch.
- A short `STATION.md` in the repo: what was built, the wiring, the test tables and what is still open.
- Recordings of real tests in `test/recordings-station/`.
