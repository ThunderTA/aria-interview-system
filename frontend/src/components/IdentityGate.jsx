import { useEffect, useRef, useState } from "react";
import Notice from "./Notice";
import { skipIdentity, verifyIdentity } from "../api/sessions";
import { CAMERA_REQUIRED_MESSAGES, METHOD_REASONS } from "../constants/identity";
import "./IdentityGate.css";

// A short burst rather than one frame: a blink or a head turn in a single
// frame shouldn't fail the check, and consistent frames prove one steady face.
const BURST_FRAMES = 3;
const BURST_GAP_MS = 350;
const SUCCESS_PAUSE_MS = 900;

const FAILURE_TITLES = {
  FACE_NOT_DETECTED: "We couldn't see your face clearly.",
  MULTIPLE_FACES_DETECTED: "More than one person is in frame.",
  IDENTITY_MISMATCH: "That didn't match your resume photo.",
};

/**
 * Start-of-interview identity check. Blocks the first question until the
 * candidate is verified (or, where the backend allows it, continues with the
 * outcome recorded).
 */
export default function IdentityGate({ sessionId, identity, camera, onIdentityChange }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [requestError, setRequestError] = useState(null);
  const [engineUnavailable, setEngineUnavailable] = useState(false);
  const [passed, setPassed] = useState(false);
  const successTimer = useRef(null);

  const usesResumePhoto = identity.method === "resume_photo";

  useEffect(() => () => clearTimeout(successTimer.current), []);

  const captureBurst = async () => {
    const frames = [];
    for (let i = 0; i < BURST_FRAMES; i += 1) {
      if (i > 0) await new Promise((resolve) => setTimeout(resolve, BURST_GAP_MS));
      const frame = await camera.captureStill();
      if (frame) frames.push(frame);
    }
    return frames;
  };

  const finish = (outcome) => {
    setPassed(true);
    successTimer.current = setTimeout(() => onIdentityChange(outcome.identity), SUCCESS_PAUSE_MS);
  };

  const runVerify = async ({ continueUnmatched = false } = {}) => {
    setBusy(true);
    setRequestError(null);
    try {
      const frames = await captureBurst();
      if (frames.length === 0) {
        setRequestError("Your camera isn't sending a picture yet. Wait a moment, then try again.");
        return;
      }
      const outcome = await verifyIdentity(sessionId, frames, { continueUnmatched });
      setEngineUnavailable(false);
      if (outcome.passed) {
        setResult(null);
        finish(outcome);
      } else {
        setResult(outcome);
        // Still pending, so the gate stays up - this just keeps attempt counts current.
        onIdentityChange(outcome.identity);
      }
    } catch (err) {
      if (err.response?.status === 503) setEngineUnavailable(true);
      setRequestError(
        err.response?.data?.detail || "Couldn't reach ARIA to verify you. Check your connection and try again."
      );
    } finally {
      setBusy(false);
    }
  };

  const runSkip = async () => {
    setBusy(true);
    setRequestError(null);
    try {
      finish(await skipIdentity(sessionId));
    } catch (err) {
      setEngineUnavailable(false);
      setRequestError(err.response?.data?.detail || "Couldn't continue. Try verifying again.");
    } finally {
      setBusy(false);
    }
  };

  const intro = usesResumePhoto
    ? "Your resume has a profile photo. Before the first question we'll compare it with your camera, then quietly re-check it's still you every " +
      `${identity.check_interval_seconds} seconds.`
    : `${METHOD_REASONS[identity.method_reason] ?? "There's no resume photo to compare with"}, so you'll verify once with your camera instead. That capture becomes the reference we re-check against every ${identity.check_interval_seconds} seconds.`;

  const frameState = passed ? "passed" : busy ? "checking" : result ? "failed" : "idle";

  return (
    <section className="identity-gate">
      <div className="identity-gate__intro">
        <p className="identity-gate__eyebrow">Before your first question</p>
        <h1 className="identity-gate__title">Confirm it's you</h1>
        <p className="identity-gate__sub">{intro}</p>

        <ul className="identity-gate__tips">
          <li>Face the camera with your whole face in view</li>
          <li>Use even light - avoid a bright window behind you</li>
          <li>Make sure you're the only person in frame</li>
        </ul>

        <p className="identity-gate__privacy">
          Camera frames are analysed and discarded, never stored. Your face reference is encrypted, and
          this session's copy is deleted when the interview ends.
        </p>
      </div>

      <div className="identity-gate__camera">
        <div className={`identity-gate__frame identity-gate__frame--${frameState}`}>
          <video
            ref={camera.attachVideo}
            className="identity-gate__video"
            muted
            playsInline
            hidden={!camera.enabled}
          />
          {camera.enabled && !passed && <span className="identity-gate__guide" aria-hidden="true" />}
          {!camera.enabled && (
            <div className="identity-gate__placeholder">
              <span className="camera-frame__icon" aria-hidden="true" />
              <p>Camera off</p>
            </div>
          )}
          {busy && camera.enabled && <span className="identity-gate__status">Checking...</span>}
          {passed && (
            <span className="identity-gate__status identity-gate__status--passed">
              <span className="identity-gate__tick" aria-hidden="true" />
              Confirmed
            </span>
          )}
        </div>

        <div className="identity-gate__feedback" aria-live="polite">
          {!camera.enabled && camera.errorCode && (
            <Notice title="Your camera is needed for this interview.">
              {CAMERA_REQUIRED_MESSAGES[camera.errorCode]}
            </Notice>
          )}

          {requestError && !passed && <Notice title="Verification didn't run.">{requestError}</Notice>}

          {result && !passed && !requestError && (
            <Notice title={FAILURE_TITLES[result.outcome] ?? "Verification didn't pass."}>
              {result.message}
              {result.identity.can_continue_unmatched &&
                " If your resume photo is old or low quality, you can continue - the mismatch will be noted in your report."}
            </Notice>
          )}
        </div>

        <div className="identity-gate__actions">
          {!camera.enabled ? (
            <button type="button" className="identity-gate__primary" onClick={camera.start}>
              {camera.errorCode ? "Try the camera again" : "Turn on camera"}
            </button>
          ) : (
            <button
              type="button"
              className="identity-gate__primary"
              onClick={() => runVerify()}
              disabled={busy || passed}
            >
              {busy
                ? "Checking..."
                : result
                  ? "Try again"
                  : usesResumePhoto
                    ? "Match my resume photo"
                    : "Verify with my camera"}
            </button>
          )}

          {camera.enabled && identity.can_continue_unmatched && !passed && (
            <button
              type="button"
              className="identity-gate__secondary"
              onClick={() => runVerify({ continueUnmatched: true })}
              disabled={busy}
            >
              Continue without a match
            </button>
          )}

          {engineUnavailable && !passed && (
            <button type="button" className="identity-gate__secondary" onClick={runSkip} disabled={busy}>
              Continue without verification
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
