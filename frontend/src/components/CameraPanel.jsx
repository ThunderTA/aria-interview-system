import "./CameraPanel.css";

/**
 * Webcam preview shown alongside the question.
 *
 * Mirrored, because an un-mirrored view of yourself is disconcerting — this is
 * what every video-call app does, and it only affects the preview, not the
 * frames sent for analysis.
 */
export default function CameraPanel({ camera, recording }) {
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
          ref={camera.videoRef}
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
      </div>

      {camera.enabled ? (
        <button type="button" className="camera-toggle" onClick={camera.stop}>
          Turn camera off
        </button>
      ) : (
        <button type="button" className="camera-toggle camera-toggle--on" onClick={camera.start}>
          Turn camera on
        </button>
      )}

      <p className="interview-panel__hint">
        {camera.error ??
          (camera.enabled
            ? "Eye contact, expression and posture are measured from frames sampled while you answer. Nothing is recorded or uploaded — frames are analysed and discarded."
            : "Optional. Without it you'll still be scored on content and delivery.")}
      </p>
    </div>
  );
}
