# BirdLU

Letters sung as bird calls. One device sings a message, another listens through its microphone and writes it back out. No network, no pairing — only sound.

- **Send** (`send.html`) — type a message, hear it as a chirp alphabet, read it as a score.
- **Listen** (`listen.html`) — decode calls from the microphone, a recording, or an in-page simulation with noise and echo.

## The chirp alphabet

Every letter is one call built from four properties:

| Property  | Values                                   |
|-----------|------------------------------------------|
| Pitch band| B1–B4, centred at 2.4 / 3.2 / 4.0 / 4.8 kHz |
| Direction | rising ↑ or falling ↓ across 700 Hz       |
| Shape     | straight, or a hook that turns back at the end |
| Length    | 70 ms for the 16 most common letters, 130 ms for the rest |

4 × 2 × 2 × 2 = 32 calls: `a–z . , ? ! ' -`. Spaces are pauses. A high opening call (above 5 kHz) and a low closing trill (below 2 kHz) frame each message; the listener uses the opening call to calibrate tempo and pitch. Accents fold to the base letter (é → e, ß → ss).

## Decoder (rule-based baseline)

1. FFT pitch tracking every ~2.7 ms between 1.2 and 7.4 kHz.
2. Calls are cut at silences, loudness dips (echo tails) and pitch jumps.
3. The opening call sets pitch and tempo.
4. Each call is measured (band, direction, turn-back, duration) and looked up.
5. The closing trill, or a long silence, ends the message.

## Simulation

```
node test/simulate.mjs      # error rate per condition
node test/simulate.mjs -v   # with sent/heard pairs
```

Current baseline (synthetic audio): 0 % in quiet, hiss, train rumble, nearby voices and small rooms; ~2 % in a museum-sized hall; ~5 % hall + voices; fails when voices are louder than the calls (6 dB). Errors in halls are mostly missed hooks and calls stretched by echo — the place where a small trained classifier would help next.

## Run locally

The microphone needs HTTPS or `localhost`:

```
python3 -m http.server 8000
```

Then open http://localhost:8000.
