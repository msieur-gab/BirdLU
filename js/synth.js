// The bird synthesizer in the browser: a port of lab/synth.py `sing`, `trim` and lab/variants.py `level`.
// A letter is a few numbers (a model): pitch (Hz), one note's pitch line (shape, octaves from pitch) and loudness
// (env, 0–1) at 48 points, overtones, how many notes, how far apart (period, s), how long (note_dur, s), and the
// drift from note to note (pitch_drift in octaves, level_drift in dB). This is what a device would run.
// Same steps as the Python; only the small random wobble differs (another random generator), as it would on a device.

export const SR = 44100;

function rng(seed) {
  let a = seed >>> 0;
  const u = () => {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return (mean = 0, sd = 1) => mean + sd * Math.sqrt(-2 * Math.log(1 - u())) * Math.cos(2 * Math.PI * u());
}

// value of the points v (evenly spaced over 0..1) at x
const at = (v, x) => {
  const p = Math.min(1, Math.max(0, x)) * (v.length - 1), i = Math.min(v.length - 2, Math.floor(p));
  return v[i] + (v[i + 1] - v[i]) * (p - i);
};

/** The letter as sound (Float32Array at SR), before trimming and levelling. */
export function singModel(m, seed = 0, wobble = 0.004) {
  const N = rng(seed + 1), sr = SR;
  const n = Math.floor((m.period * (m.notes - 1) + m.note_dur + 0.05) * sr), y = new Float32Array(n);
  let tStart = 0;
  for (let i = 0; i < m.notes; i++) {
    const centre = m.pitch * Math.pow(2, m.pitch_drift * i + N(0, 0.006));
    const lvl = Math.pow(10, (m.level_drift * i + N(0, 0.8)) / 20);
    const k = Math.floor(m.note_dur * (1 + N(0, 0.03)) * sr);
    if (k < 2) continue;
    // a slow random wobble: real voices never hold a perfectly clean line (noise averaged over 200 samples)
    const noise = new Float32Array(k + 200), w = new Float32Array(k);
    for (let j = 0; j < noise.length; j++) noise[j] = N();
    let acc = 0, sq = 0, mean = 0;
    for (let j = 0; j < 200; j++) acc += noise[j];
    for (let j = 0; j < k; j++) { w[j] = acc / 200; acc += noise[j + 200] - noise[j]; mean += w[j]; }
    mean /= k;
    for (let j = 0; j < k; j++) sq += (w[j] - mean) ** 2;
    const sd = Math.sqrt(sq / k) + 1e-9;
    const r = Math.min(Math.floor(0.003 * sr), k >> 2);     // soft edges: no clicks between notes
    const o = Math.floor(tStart * sr), ot = m.overtones.map((a, h) => centre * (h + 2) < sr / 2 - 500 ? a : 0);
    let phase = 0;
    for (let j = 0; j < k && o + j < n; j++) {
      const tt = j / (k - 1);
      const f = centre * Math.pow(2, at(m.shape, tt)) * (1 + wobble * w[j] / sd);
      phase += 2 * Math.PI * f / sr;
      let env = Math.max(0, at(m.env, tt)) * lvl;
      if (r > 0 && j < r) env *= Math.sin(j / (r - 1 || 1) * Math.PI / 2) ** 2;
      if (r > 0 && j >= k - r) env *= Math.cos((j - (k - r)) / (r - 1 || 1) * Math.PI / 2) ** 2;
      let s = Math.sin(phase);
      for (let h = 0; h < ot.length; h++) if (ot[h]) s += ot[h] * Math.sin((h + 2) * phase);
      y[o + j] += env * s;
    }
    tStart += m.period + m.accel * i;
  }
  return y;
}

/** Drop the near-silence before the first note and after the last one. */
export function trim(y, belowDb = 40, keepMs = 3) {
  const env = new Float32Array(y.length);
  let acc = 0, mx = 0;
  for (let i = 0; i < y.length + 32; i++) {       // moving average of |y| over 64 samples, centred
    if (i < y.length) acc += Math.abs(y[i]);
    if (i >= 64) acc -= Math.abs(y[i - 64]);
    const c = i - 32;
    if (c >= 0 && c < y.length) { env[c] = acc / 64; mx = Math.max(mx, env[c]); }
  }
  const th = mx * Math.pow(10, -belowDb / 20);
  let a = 0, b = y.length - 1;
  while (a < y.length && env[a] <= th) a++;
  while (b > a && env[b] <= th) b--;
  if (a >= y.length) return y;
  const k = Math.floor(keepMs / 1000 * SR);
  return y.slice(Math.max(0, a - k), b + k);
}

/** Same loudness for every letter: the loudest fifth of the samples at 0.25 RMS. */
export function level(y) {
  const s = Float32Array.from(y, Math.abs).sort(), n = Math.max(1, Math.floor(y.length / 5));
  let sq = 0;
  for (let i = s.length - n; i < s.length; i++) sq += s[i] * s[i];
  const g = 0.25 / (Math.sqrt(sq / n) + 1e-9);
  return y.map(v => v * g);
}

/** An opening or closing call from its numbers (birds/draw/frames.json): each note starts at `at` seconds, at `level`,
 *  sung from its model like a letter; an overtone that would rise above frame.top_hz is left out.
 *  The twin of lab/draw_models.py frame_sound. */
export function frameSound(frame) {
  let end = 0;
  for (const n of frame.notes) end = Math.max(end, n.at);
  const y = new Float32Array(Math.floor((end + 1) * SR));
  for (const n of frame.notes) {
    const top = n.model.pitch * Math.pow(2, Math.max(...n.model.shape));
    const m = { ...n.model, overtones: n.model.overtones.map((o, h) => top * (h + 2) <= frame.top_hz ? o : 0) };
    const z = singModel(m, n.seed), o = Math.floor(n.at * SR);
    for (let i = 0; i < z.length && o + i < y.length; i++) y[o + i] += n.level * z[i];
  }
  return level(trim(y));
}

/** A letter ready for the voice, as the lab writes its WAV files. */
export const letterSound = m => level(trim(singModel(m, m.seed ?? 0)));

/** The pitch (Hz) and loudness (0–1) of the model along time, for drawing: [{t0, t1, f(u), a(u)}] per note. */
export function contour(m) {
  const out = [];
  let t = 0;
  for (let i = 0; i < m.notes; i++) {
    const centre = m.pitch * Math.pow(2, m.pitch_drift * i), lvl = Math.pow(10, m.level_drift * i / 20);
    out.push({ t0: t, t1: t + m.note_dur, f: u => centre * Math.pow(2, at(m.shape, u)), a: u => Math.max(0, at(m.env, u)) * lvl });
    t += m.period + m.accel * i;
  }
  return out;
}
