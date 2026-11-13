// Run: node test/simulate.mjs
// Sings messages, degrades them (noise, echo, tempo, pitch), decodes, reports the error rate.
import { build, renderSamples } from "../js/chirp.js?v=5";
import { decodeBuffer, cer, addEcho, addNoise, addSpeaker } from "../js/decoder.js?v=5";

const SR = 48000;
const MESSAGES = [
  "you are not alone on this train",
  "the quick brown fox jumps over the lazy dog",
  "slow letters travel with the line",
  "is anyone else watching the river?",
  "write back, it's a long way to ulm!",
  "l'été arrive, où es-tu?"
];

const CONDITIONS = [
  { name: "clean", tempo: 1, pitch: 1 },
  { name: "fast + high", tempo: 1.4, pitch: 1.2 },
  { name: "slow + low", tempo: 0.7, pitch: 0.85 },
  { name: "white noise 20 dB", noise: ["white", 20] },
  { name: "white noise 10 dB", noise: ["white", 10] },
  { name: "train rumble 0 dB", noise: ["rumble", 0] },
  { name: "voices 15 dB", noise: ["voices", 15] },
  { name: "voices 6 dB", noise: ["voices", 6] },
  { name: "small room echo", echo: [0.25, 0.6] },
  { name: "hall echo", echo: [0.35, 1.6] },
  { name: "hall + voices 10 dB", echo: [0.35, 1.6], noise: ["voices", 10] },
  { name: "small speaker", speaker: 2.5 },
  { name: "speaker pushed hard", speaker: 6 },
  { name: "speaker + small room", speaker: 2.5, echo: [0.25, 0.6] },
  { name: "speaker + room + voices", speaker: 2.5, echo: [0.25, 0.6], noise: ["voices", 12] }
];

let all = [];
for (const c of CONDITIONS) {
  const rates = [];
  const confusions = [];
  MESSAGES.forEach((m, k) => {
    const sched = build(m, c.tempo || 1);
    let x = renderSamples(sched, SR, c.pitch || 1);
    if (c.speaker) x = addSpeaker(x, SR, c.speaker);
    if (c.echo) x = addEcho(x, SR, c.echo[0], c.echo[1]);
    if (c.noise) x = addNoise(x, SR, c.noise[0], c.noise[1], 7 + k);
    const got = decodeBuffer(x, SR);
    const hyp = got.length ? got[0].text : "";
    const r = cer(sched.text, hyp);
    rates.push(r);
    if (r > 0) confusions.push(`    sent: ${sched.text}\n    got:  ${hyp}${got.length ? (got[0].complete ? "" : "  (no closing)") : "  (no opening found)"}`);
  });
  const avg = rates.reduce((a, b) => a + b, 0) / rates.length;
  all.push(avg);
  console.log(`${c.name.padEnd(22)} error ${(avg * 100).toFixed(1).padStart(5)}%`);
  if (process.argv.includes("-v")) confusions.forEach(s => console.log(s));
}
console.log(`\naverage error ${(all.reduce((a, b) => a + b, 0) / all.length * 100).toFixed(1)}%`);
