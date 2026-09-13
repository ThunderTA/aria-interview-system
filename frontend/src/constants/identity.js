// Values mirror backend/app/models/identity.py.

export const METHOD_LABELS = {
  resume_photo: "Resume photo",
  camera: "Camera verification",
};

/** Why a candidate verifies by camera instead of their resume photo. */
export const METHOD_REASONS = {
  no_resume_photo: "We didn't find a photo in your resume",
  resume_photo_unusable: "The photo in your resume wasn't clear enough to use",
  photo_analysis_unavailable: "Your resume photo couldn't be analysed",
  photo_reference_unavailable: "Your saved resume photo has expired",
};

/** Resume upload: what was found, phrased for the candidate. */
export const PHOTO_MESSAGES = {
  usable: "Profile photo found — you'll match it with your camera when the interview starts.",
  not_found: "No profile photo found. That's fine — you'll verify once with your camera before the interview starts.",
  unusable: "Your resume photo isn't usable for verification, so you'll verify once with your camera instead.",
  unavailable: "Your resume photo couldn't be checked right now, so you'll verify once with your camera instead.",
};

export const PHOTO_REASONS = {
  multiple_faces: "it shows more than one person",
  too_small: "the face is too small",
  too_dark: "the image is too dark",
  blurry: "the image is too blurry",
};

/** Live guidance for a check that couldn't see a usable face. */
export const HINT_MESSAGES = {
  too_dark: "It's too dark to see your face — add some light.",
  blurry: "The picture is blurry — hold still.",
  too_small: "Move a little closer to the camera.",
  camera_off: "Your camera is off — turn it back on for identity checks.",
  unreadable_frame: "The camera picture couldn't be read.",
};

export const STATUS_LABELS = {
  verified: "Verified",
  flagged: "Flagged",
  inconclusive: "Inconclusive",
  not_verified: "Not verified",
};

export const EVENT_LABELS = {
  PERSISTENT_MISMATCH: "A different face was seen",
  MULTIPLE_PEOPLE: "More than one person in frame",
  START_UNMATCHED: "Resume photo didn't match at the start",
  VERIFICATION_UNAVAILABLE: "Verification couldn't run",
};

export const CAMERA_REQUIRED_MESSAGES = {
  denied:
    "Camera access is blocked. Allow it from the camera icon in your browser's address bar, then try again.",
  not_found: "No camera was found. Connect a webcam, then try again.",
  in_use: "Your camera is being used by another app. Close that app, then try again.",
  unsupported: "This browser can't access a camera. Try a current version of Chrome, Edge, Firefox or Safari.",
  stopped: "Your camera stopped. Turn it back on to continue.",
  unknown: "The camera couldn't be started. Check it's connected, then try again.",
};
