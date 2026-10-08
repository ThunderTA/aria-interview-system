// States mirror cv_analysis.py. The backend sends a label with every check;
// these are the fallbacks and the colour each state reads in.

export const ATTENTION_LABELS = {
  on_camera: "Looking at the camera",
  looking_left: "Looking away to your left",
  looking_right: "Looking away to your right",
  looking_down: "Looking down",
  looking_up: "Looking up",
  turned_away: "Turned away from the camera",
  eyes_closed: "Eyes closed",
  no_face: "Not in frame",
};

/** ok = on camera, away = looking elsewhere, warn = can't see the candidate. */
export const ATTENTION_TONES = {
  on_camera: "ok",
  looking_left: "away",
  looking_right: "away",
  looking_down: "away",
  looking_up: "away",
  turned_away: "warn",
  eyes_closed: "away",
  no_face: "warn",
};

export function attentionLabel(state, fallback) {
  return ATTENTION_LABELS[state] ?? fallback ?? "Checking...";
}
