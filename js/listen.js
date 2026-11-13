import { build, renderSamples, encodeWav } from "./chirp.js?v=5";
import { Decoder, decodeBuffer, cer, addEcho, addNoise } from "./decoder.js?v=5";

const $ = id => document.getElementById(id);
const btn = $("listen"), pill = $("state"), live = $("live"), inbox = $("inbox");
const spectro = $("spectro"), levelEl = $("level"), rateEl = $("rate"), seglog = $("seglog");

let ctx = null, stream = null, node = null, src = null, decoder = null, wakeLock = null;
let rec = null; // { chunks, length, sampleRate } while keeping a recording
const MAX_REC_SECONDS = 300;
const segLines = [];

function setState(state, text) { pill.dataset.state = state; pill.textContent = text; }

function showLive(text, receiving) {
  live.classList.toggle("idle", !receiving && !text);
  live.textContent = text || (receiving ? "" : "Waiting for an opening call…");
  if (receiving) { const c = document.createElement("span"); c.className = "caret"; live.appendChild(c); }
}

function addToInbox(m, source) {
  const li = document.createElement("li");
  if (!m.complete) li.className = "partial";
  const t = document.createElement("span"); t.className = "text"; t.textContent = m.text || "(nothing readable)";
  const meta = document.createElement("span"); meta.className = "meta";
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  meta.textContent = `${time} · ${source} · pitch ${Math.round((m.pitch - 1) * 100)}% · ${m.complete ? "complete" : "no closing call heard"}`;
  li.append(t, meta);
  inbox.prepend(li);
}

function logSeg(s) {
  segLines.push(`${s.t0.toFixed(2)}s  ${String(Math.round(s.center)).padStart(5)} Hz  ${s.dir.padEnd(4)}  wobble ${String(Math.round(s.wobble)).padStart(4)}  ${Math.round(s.dur * 1000)} ms`);
  if (segLines.length > 40) segLines.shift();
  seglog.textContent = segLines.join("\n");
}

// ---------- spectrogram ----------
const sctx = spectro.getContext("2d");
let col = 0, maxDb = -60;
function sizeSpectro() { spectro.width = Math.max(200, Math.round(spectro.clientWidth)); spectro.height = 180; clearSpectro(); }
function clearSpectro() {
  sctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--paper").trim();
  sctx.fillRect(0, 0, spectro.width, spectro.height);
}
function hexToRgb(h) {
  h = h.replace("#", ""); if (h.length === 3) h = h.split("").map(x => x + x).join("");
  const n = parseInt(h, 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
let colors = null;
function readColors() {
  const cs = getComputedStyle(document.documentElement);
  colors = { paper: hexToRgb(cs.getPropertyValue("--paper").trim()), ink: hexToRgb(cs.getPropertyValue("--ink").trim()), hot: hexToRgb(cs.getPropertyValue("--long").trim()) };
}
function drawColumn(f) {
  if (++col % 3) return;
  if (!colors) readColors();
  const W = spectro.width, H = spectro.height, p = f.power;
  sctx.drawImage(spectro, -1, 0);
  const img = sctx.createImageData(1, H);
  maxDb = Math.max(maxDb - 0.05, f.db);
  for (let y = 0; y < H; y++) {
    const i = Math.min(p.length - 1, Math.floor((1 - y / H) * p.length));
    const db = 10 * Math.log10(p[i] + 1e-12);
    const v = Math.max(0, Math.min(1, (db - (maxDb - 50)) / 50));
    const to = f.active ? colors.hot : colors.ink;
    for (let k = 0; k < 3; k++) img.data[y * 4 + k] = colors.paper[k] + (to[k] - colors.paper[k]) * v;
    img.data[y * 4 + 3] = 255;
  }
  sctx.putImageData(img, W - 1, 0);
  levelEl.textContent = `peak ${(f.f / 1000).toFixed(2)} kHz · clarity ${Math.max(0, f.snr).toFixed(0)} dB`;
}

// ---------- microphone ----------
const WORKLET = `class Tap extends AudioWorkletProcessor{constructor(){super();this.b=new Float32Array(2048);this.n=0}
process(i){const c=i[0]&&i[0][0];if(c){for(let k=0;k<c.length;k++){this.b[this.n++]=c[k];if(this.n===this.b.length){this.port.postMessage(this.b.slice(0));this.n=0}}}return true}}
registerProcessor('tap',Tap);`;

async function start() {
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    ctx = new AC();
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    await ctx.resume();
    src = ctx.createMediaStreamSource(stream);
    decoder = new Decoder(ctx.sampleRate, { on: {
      frame: drawColumn,
      segment: logSeg,
      state: s => { if (s === "receiving") { setState("receiving", "Receiving a letter"); showLive("", true); } else setState("listening", "Listening"); },
      letter: (ch, info, text) => showLive(text, true),
      message: m => { addToInbox(m, "microphone"); showLive(m.text, false); }
    } });
    rec = $("keepRec").checked ? { chunks: [], length: 0, sampleRate: ctx.sampleRate } : null;
    $("recOut").textContent = rec ? "Recording what the phone hears (up to 5 minutes)." : "";
    const feed = d => {
      decoder.push(d);
      if (rec && rec.length < MAX_REC_SECONDS * rec.sampleRate) { rec.chunks.push(d); rec.length += d.length; }
    };
    if (ctx.audioWorklet) {
      const url = URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" }));
      await ctx.audioWorklet.addModule(url);
      node = new AudioWorkletNode(ctx, "tap");
      node.port.onmessage = e => feed(e.data);
      const mute = ctx.createGain(); mute.gain.value = 0;
      src.connect(node); node.connect(mute); mute.connect(ctx.destination);
    } else {
      node = ctx.createScriptProcessor(2048, 1, 1);
      node.onaudioprocess = e => feed(new Float32Array(e.inputBuffer.getChannelData(0)));
      const mute = ctx.createGain(); mute.gain.value = 0;
      src.connect(node); node.connect(mute); mute.connect(ctx.destination);
    }
    rateEl.textContent = `${ctx.sampleRate} Hz`;
    setState("listening", "Listening");
    showLive("", false);
    btn.textContent = "Stop listening"; btn.setAttribute("aria-pressed", "true");
    keepAwake();
  } catch (e) {
    stop();
    const why = e && e.name === "NotAllowedError" ? "Microphone access was refused. Allow it in the browser settings and try again."
      : !window.isSecureContext ? "The microphone only works over HTTPS. Open the page from its https:// address."
      : "Could not start the microphone: " + (e && e.message ? e.message : e);
    setState("error", "Microphone off"); live.classList.add("idle"); live.textContent = why;
  }
}

function offerRecording() {
  if (!rec || !rec.length) return;
  const all = new Float32Array(rec.length); let o = 0;
  for (const c of rec.chunks) { all.set(c, o); o += c.length; }
  const blob = encodeWav(all, rec.sampleRate), url = URL.createObjectURL(blob);
  const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
  const a = document.createElement("a"); a.href = url; a.download = `birdlu-heard-${stamp}.wav`;
  a.textContent = `Download what the phone heard (${Math.round(rec.length / rec.sampleRate)} s, ${Math.round(blob.size / 1024)} KB)`;
  const out = $("recOut"); out.textContent = ""; out.append(a);
  rec = null;
}

function stop() {
  if (decoder) decoder.end();
  offerRecording();
  try { if (node) node.disconnect(); if (src) src.disconnect(); } catch (e) { /* already gone */ }
  if (stream) stream.getTracks().forEach(t => t.stop());
  if (ctx) ctx.close();
  ctx = stream = node = src = decoder = null;
  if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
  setState("off", "Microphone off");
  btn.textContent = "Start listening"; btn.setAttribute("aria-pressed", "false");
}

async function keepAwake() {
  try { if ("wakeLock" in navigator) wakeLock = await navigator.wakeLock.request("screen"); } catch (e) { /* not supported */ }
}
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && ctx && !wakeLock) keepAwake(); });

btn.addEventListener("click", () => { if (ctx) stop(); else start(); });

// ---------- simulation ----------
$("simRun").addEventListener("click", () => {
  const out = $("simOut");
  out.textContent = "Singing and decoding…";
  setTimeout(() => {
    const sr = 48000;
    const sched = build($("simText").value, +$("simTempo").value);
    let x = renderSamples(sched, sr, 1);
    const [mix, rt] = $("simEcho").value.split(":").map(Number);
    if (mix > 0) x = addEcho(x, sr, mix, rt);
    const nz = $("simNoise").value;
    if (nz !== "none") { const [kind, snr] = nz.split(":"); x = addNoise(x, sr, kind, +snr, Math.floor(Math.random() * 1e6)); }
    const got = decodeBuffer(x, sr);
    const hyp = got.length ? got[0].text : "";
    const err = cer(sched.text, hyp);
    out.textContent = `sent      ${sched.text}\nheard     ${hyp || "(no opening call found)"}\nerrors    ${(err * 100).toFixed(1)}% of letters`;
  }, 20);
});

// ---------- recording ----------
$("file").addEventListener("change", async e => {
  const f = e.target.files[0], out = $("fileOut");
  if (!f) return;
  out.textContent = "Decoding…";
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    const ac = new AC();
    const buf = await ac.decodeAudioData(await f.arrayBuffer());
    const x = new Float32Array(buf.length);
    for (let c = 0; c < buf.numberOfChannels; c++) { const d = buf.getChannelData(c); for (let i = 0; i < d.length; i++) x[i] += d[i] / buf.numberOfChannels; }
    ac.close();
    const msgs = decodeBuffer(x, buf.sampleRate);
    msgs.forEach(m => addToInbox(m, "recording"));
    out.textContent = msgs.length ? msgs.map((m, i) => `${i + 1}. ${m.text}${m.complete ? "" : "  (no closing call)"}`).join("\n") : "No opening call found in this recording.";
  } catch (err) {
    out.textContent = "This file could not be read as audio. Try an .m4a, .mp3 or .wav file.";
  }
});

const redraw = () => { colors = null; sizeSpectro(); };
try { matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw); } catch (e) { /* old Safari */ }
new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
addEventListener("resize", sizeSpectro);
sizeSpectro();
