// Decodes in the background, so the page (and its microphone) never waits for it.
import { loadVoice, Decoder } from "./birdsong.js?v=6";

let dec = null;
const ready = loadVoice("../birds/voice/").then(V => { dec = new Decoder(V); });

self.onmessage = async e => {
  const m = e.data;
  await ready;
  if (m.type === "scan") {
    // look for an opening and a closing in the last seconds; decode the message once both are heard
    const { x, sr, start, openMin, closeMin } = m;
    const f = dec.findFrames(x, sr);
    const out = { id: m.id, f, start };
    if (f.openScore >= openMin && f.close !== null && f.closeScore >= closeMin && f.closeEnd <= x.length / sr - 0.3) {
      const a = Math.max(0, Math.round((f.open - 0.3) * sr)), b = Math.min(x.length, Math.round((f.closeEnd + 0.4) * sr));
      const slice = x.slice(a, b), t0 = performance.now();
      out.r = dec.decode(slice, sr);
      out.r0 = dec.decode(slice, sr, { echo: false });
      out.ms = Math.round(performance.now() - t0);
      out.a = a; out.b = b; out.slice = slice;
      self.postMessage(out, [slice.buffer]);
      return;
    }
    self.postMessage(out);
  }
};
