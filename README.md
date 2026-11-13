# BirdLU

Letters sung as bird calls. One device sings a message, another listens through its microphone and writes it back out. No network, no pairing — only sound.

- **Send** (`send.html`) — type a message, hear it as a chirp alphabet, read it as a score, save it as MP3 or WAV.
- **Listen** (`listen.html`) — decode calls from the microphone, a recording, or an in-page simulation with noise and echo.

## The chirp alphabet (v2)

- **Vowels** are their own family: a two-note call, rising ("chi-wee") or falling ("pee-oo"). a e i o u y, plus é and è.
- **Consonants** are one call: pitch band × direction (↑/↓) × texture (smooth sweep or trill) × length (short/long).
- **Bands** at 2.9 / 3.6 / 4.3 / 5.0 kHz. The most common letters (e a t n s r) sit in the middle two, which small speakers carry best.
- **Spaces** are pauses. A high opening call (above 5.5 kHz) and a low closing trill (below 2.5 kHz) frame each message; the listener calibrates tempo and pitch on the opening call.
- Other accents fold to the base letter (à → a, ü → u, ß → ss).

v1 used a "hook" (a turn-back at the end of a call) as one property. It got lost on real speakers and sounded artificial, so v2 replaces it with the trill and gives vowels their own two-note shape.

## Decoder (rule-based baseline)

1. FFT pitch tracking every ~2.7 ms between 1.2 and 7.4 kHz.
2. Calls are cut at silences, loudness dips (echo tails) and pitch jumps.
3. The opening call sets pitch and tempo.
4. Two short notes close together with a pitch jump become a vowel; other calls are measured (band, slope direction, wobble for trills, duration) and looked up. Unpaired short notes are treated as echo and skipped.
5. The closing trill, or a long silence, ends the message.

## Simulation

```
node test/simulate.mjs      # synthetic audio: error rate per condition
node test/simulate.mjs -v   # with sent/heard pairs
node test/recordings.mjs    # real recordings from test/recordings/
```

`test/recordings/` holds what a phone actually heard (Listen → "Keep a recording"), so real rooms can be replayed after every decoder change. First set (room1: PC → Bluetooth speaker → Android phone at 30–50 cm): 3.0 % average error, down from 10 % before the decoder learned to stitch calls cut in two by loudness dips and to accept weak second vowel notes.

Current baseline (v2, synthetic audio): 0 % in quiet, hiss, train rumble, nearby voices, small rooms and a simulated small speaker (also pushed hard, with room and voices); ~9 % in a museum-sized hall; fails when voices are louder than the calls. The simulated speaker does not yet reproduce the failures seen in a real room, so real recordings (Listen → "Keep a recording") are the next reference.

## Third-party

MP3 export uses [lamejs](https://github.com/zhuker/lamejs) 1.2.1 (LGPL-3.0), vendored in `js/vendor/` with its licence.

## Run locally

The microphone needs HTTPS or `localhost`:

```
python3 -m http.server 8000
```

Then open http://localhost:8000.
