# BirdLU plan

Letters sung as bird calls. One device sings a short message, another listens and writes it back out. The aim: open, slow letters in public places, and a way to bring back birdsong that traffic and daily life have drowned out in cities.

## Where we are

- **Send** and **Listen** pages are live on GitHub Pages, with a rule-based decoder and MP3/WAV export.
- In simulation, letters decode with no errors in quiet rooms and about 2% errors in a hall.
- In the real test (PC → Bluetooth speaker → phone at 30–50 cm), the opening call and pitch calibration work, but common letters are misread.
- **Cause:** e, t, a and o all sit in the lowest band (2.4 kHz) and differ only by direction and the hook. Small speakers and phone processing hurt that band most, the hook gets lost, and it sounds artificial.

## Step 1: fix the alphabet

- Spread the vowels across bands and give them their own family, a feature only vowels use, so a misheard vowel stays a vowel.
- Move the most common letters to the bands that survive small speakers best, around 3–4.5 kHz.
- Replace the hook with something more natural and sturdier. Candidates: a fast trill, a two-note call, or a difference in attack. Decide by ear and by test.
- **Test protocol:** fixed test sentences, at 30 cm, 1 m and 2 m, through the Bluetooth speaker and the laptop speaker. Record what the phone hears so the same audio can be replayed in simulation.
- **Done when:** fewer than 2% of letters are wrong at 1 m in a quiet room.

## Step 2: bird syllable library

- **Species:** great tit (mésange charbonnière), blue tit (mésange bleue), European robin (rouge-gorge). Possibly blackbird, chaffinch and wren.
- **Source:** xeno-canto. Check each recording's licence; some only allow non-commercial use, which matters for museum partnerships.
- Cut recordings into short syllables, measure them, and keep the 32 most distinct.
- One idea for the vowel family: vowels from one species, consonants from another.
- Keep the synthetic alphabet as a fallback.

## Step 3: tiny model

- Rules keep doing what they do well: finding the opening call, calibrating, and cutting the sound into calls.
- A small classifier decides which syllable each call is, with a confidence score.
- Train on generated data with variations: tempo, pitch, room echo, traffic, voices, speaker and microphone colouring, real birds in the background.
- **Target:** small enough to run in the PWA (JavaScript or WebAssembly) and on an ESP32-S3 (TFLite Micro or ESP-DL), at the lowest possible power.
- Optional word-level correction, kept off for names and for French or German words.
- The model's confusion matrix shows which syllables get mixed up, and feeds back into the alphabet design.

## Step 4: station prototype

- ESP32-S3 with amplifier and speaker, I2S microphone, battery or USB power.
- Holds about 10 letters and plays them in random order, with pauses.
- **Pick-up:** people record a letter with the PWA and carry it.
- **Drop-off:** the phone sings the letter to the station, which needs the model on the ESP32. Fallback: the phone sends the text to the station over Wi-Fi, and the station turns it into song.

## Open questions

- Which replacement for the hook sounds right?
- Which recordings can be used for museum and public-service partnerships?
- How long can a letter be?
- How are dropped letters moderated before they play in a public space?
