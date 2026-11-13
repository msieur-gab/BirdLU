// Run: node test/recordings.mjs
// Decodes real recordings made with Listen → "Keep a recording", and reports the error rate.
// Expected text is taken from the file name (see EXPECTED below).
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { normalize } from "../js/chirp.js?v=5";
import { decodeBuffer, cer } from "../js/decoder.js?v=5";

const EXPECTED = {
  "not-alone-train": "you are not alone on this train",
  "quick-brown-fox": "the quick brown fox jumps over the lazy dog",
  "alphabet-check": "aeiou yéè tnsr hldc mfpg wbvk",
  "ete-arrive": "l'été arrive, ou es-tu?"
};

function readWav(file) {
  const b = fs.readFileSync(file); let o = 12, sr = 48000, ch = 1, data = null;
  while (o < b.length) {
    const id = b.toString("ascii", o, o + 4), sz = b.readUInt32LE(o + 4);
    if (id === "fmt ") { ch = b.readUInt16LE(o + 10); sr = b.readUInt32LE(o + 12); }
    if (id === "data") { data = b.subarray(o + 8, o + 8 + sz); break; }
    o += 8 + sz;
  }
  const n = data.length / 2 / ch, x = new Float32Array(n);
  for (let i = 0; i < n; i++) { let v = 0; for (let c = 0; c < ch; c++) v += data.readInt16LE((i * ch + c) * 2); x[i] = v / ch / 32768; }
  return { x, sr };
}

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), "recordings");
let total = 0, count = 0;
for (const f of fs.readdirSync(dir).filter(f => f.endsWith(".wav")).sort()) {
  const key = Object.keys(EXPECTED).find(k => f.includes(k));
  if (!key) continue;
  const { x, sr } = readWav(path.join(dir, f));
  const got = decodeBuffer(x, sr);
  const want = normalize(EXPECTED[key]), hyp = got.length ? got[0].text : "";
  const r = cer(want, hyp); total += r; count++;
  console.log(`${f.padEnd(36)} ${(r * 100).toFixed(1).padStart(5)}%   ${hyp || "(no opening found)"}`);
}
console.log(`\naverage error ${(total / count * 100).toFixed(1)}% over ${count} recordings`);
