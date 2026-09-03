// Turns a bar index into a musical note and plays it with the Web Audio API.
// Used by the waveform decoration on the auth pages — touching a bar should
// feel like tapping a tiny instrument, not a random beep.

const ROOT_FREQUENCY = 261.63; // C4
// Major pentatonic: no interval in this set sounds dissonant against another,
// so any sequence a person taps out — in order, backwards, at random — still
// sounds musical rather than jarring.
const PENTATONIC_SEMITONES = [0, 2, 4, 7, 9];

let audioContext = null;

function getContext() {
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) return null;
  if (!audioContext) audioContext = new Ctor();
  if (audioContext.state === "suspended") audioContext.resume();
  return audioContext;
}

/** Frequency for a given bar index — ascending, wrapping into a new octave every 12 bars. */
export function frequencyForIndex(index) {
  const degree = index % PENTATONIC_SEMITONES.length;
  const octave = Math.floor(index / 12);
  return ROOT_FREQUENCY * 2 ** (octave + PENTATONIC_SEMITONES[degree] / 12);
}

/** Plays a short, quiet plucked note. Fails silently if Web Audio is unavailable. */
export function playTone(frequency) {
  const ctx = getContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = "triangle";
  osc.frequency.value = frequency;

  // Fast attack, short exponential decay — a pluck, not a drone.
  gain.gain.setValueAtTime(0, now);
  gain.gain.linearRampToValueAtTime(0.16, now + 0.008);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.4);

  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(now);
  osc.stop(now + 0.42);
}
