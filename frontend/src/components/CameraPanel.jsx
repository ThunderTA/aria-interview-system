import { ATTENTION_TONES, attentionLabel } from "../constants/attention";
import { CAMERA_REQUIRED_MESSAGES, HINT_MESSAGES } from "../constants/identity";
import "./CameraPanel.css";

function identityLine(identity, lastCheck, paused) {
  if (identity.gate === "unavailable") {
    return { tone: "muted", text: "Identity checks unavailable this session" };
  }
  if (identity.warning) {
    return {
      tone: "warn",
      text:
        identity.warning.type === "MULTIPLE_FACES_DETECTED"
          ? "More than one person in frame"
          : "Couldn't confirm it's you",
    };
  }
  if (paused) return { tone: "muted", text: "Identity checks paused" };
  if (lastCheck?.outcome === "FACE_NOT_DETECTED") {
    return { tone: "muted", text: HINT_MESSAGES[lastCheck.hint] ?? "Face not visible in the last check" };
  }
  if (identity.gate === "unmatched") {
    return { tone: "muted", text: "Resume photo not matched · same-person checks on" };
  }
  return {
    tone: "ok",
    text:
      identity.method === "resume_photo" ? "Identity verified · resume photo" : "Identity verified · camera",
  };
}

/**
 * Webcam preview shown alongside the question.
 *
 * Mirrored, because an un-mirrored view of yourself is disconcerting - this is
 * what every video-call app does, and it only affects the preview, not the
 * frames sent for analysis.
 */
export default function CameraPanel({
  camera,
  recording,
  identity,
  lastCheck,
  identityPaused,
  attention,
}) {
  const identityRequired = Boolean(identity?.required);
  const line = identityRequired ? identityLine(identity, lastCheck, identityPaused) : null;
  const gazeTone = attention?.state ? (ATTENTION_TONES[attention.state] ?? "away") : null;

  return (
    <div className="interview-panel">
      <div className="camera-head">
        <p className="interview-panel__label">Camera</p>
        {camera.enabled && (
          <span className={`camera-badge${recording ? " camera-badge--live" : ""}`}>
            {recording ? "Analysing" : "On"}
          </span>
        )}
      </div>

      <div className={`camera-frame${camera.enabled ? " camera-frame--live" : ""}`}>
        <video
          ref={camera.attachVideo}
          className="camera-video"
          muted
          playsInline
          hidden={!camera.enabled}
        />
        {!camera.enabled && (
          <div className="camera-frame__placeholder">
            <span className="camera-frame__icon" aria-hidden="true" />
            <p>Camera off</p>
          </div>
        )}
        {camera.enabled && attention?.state && (
          <span className={`attention-badge attention-badge--${gazeTone}`}>
            <span className="attention-badge__dot" aria-hidden="true" />
            {attentionLabel(attention.state, attention.label)}
          </span>
        )}
      </div>

      {line && (
        <p className={`identity-line identity-line--${line.tone}`} role="status">
          <span className="identity-line__dot" aria-hidden="true" />
          {line.text}
        </p>
      )}

      {attention?.checks > 0 && (
        <p className="attention-line" role="status">
          {attention.warning ?? `Eye contact ${Math.round(attention.on_camera_share)}% so far`}
        </p>
      )}

      {camera.enabled ? (
        // Identity checks need the camera for the whole interview.
        !identityRequired && (
          <button type="button" className="camera-toggle" onClick={camera.stop}>
            Turn camera off
          </button>
        )
      ) : (
        <button type="button" className="camera-toggle camera-toggle--on" onClick={camera.start}>
          Turn camera on
        </button>
      )}

      <p className="interview-panel__hint">
        {identityRequired
          ? camera.enabled
            ? `Your identity is re-checked every ${identity.check_interval_seconds} seconds, and where you're looking is read from the camera a few times a minute. Frames are analysed and discarded - nothing is recorded.`
            : (CAMERA_REQUIRED_MESSAGES[camera.errorCode] ?? "Your camera is required for identity checks.") +
              " While it's off, checks are recorded as face not detected."
          : (camera.error ??
            (camera.enabled
              ? "Eye contact, expression and posture are measured from frames sampled while you answer. Nothing is recorded or uploaded - frames are analysed and discarded."
              : "Optional. Without it you'll still be scored on content and delivery."))}
      </p>
    </div>
  );
}
