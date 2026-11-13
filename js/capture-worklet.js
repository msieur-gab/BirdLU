// Records the microphone on the audio thread, so a busy page cannot drop sound.
// Posts blocks of 2048 samples with the frame number of their first sample.
class BirdCapture extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Float32Array(2048); this.n = 0; this.first = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      if (this.n === 0) this.first = currentFrame + i;
      this.buf[this.n++] = ch[i];
      if (this.n === this.buf.length) {
        this.port.postMessage({ frame: this.first, data: this.buf }, [this.buf.buffer]);
        this.buf = new Float32Array(2048); this.n = 0;
      }
    }
    return true;
  }
}
registerProcessor("bird-capture", BirdCapture);
