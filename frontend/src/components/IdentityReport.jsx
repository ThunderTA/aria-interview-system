import { EVENT_LABELS, METHOD_LABELS, STATUS_LABELS } from "../constants/identity";

const COUNTS = [
  ["checks", "Checks"],
  ["matches", "Matches"],
  ["mismatches", "Mismatches"],
  ["multiple_faces", "Multiple faces"],
  ["face_not_detected", "Face not detected"],
];

function formatTime(value) {
  return new Date(value).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function startResult(identity) {
  switch (identity.gate) {
    case "verified":
      return identity.method === "resume_photo"
        ? "matched resume photo at the start"
        : "verified with camera at the start";
    case "unmatched":
      return "didn't match resume photo, continued anyway";
    case "unavailable":
      return "verification couldn't run";
    default:
      return "not completed";
  }
}

function eventMeta(event) {
  if (event.type === "START_UNMATCHED") {
    return `${formatTime(event.started_at)} · after ${event.checks} attempt${event.checks === 1 ? "" : "s"}`;
  }
  if (event.type === "VERIFICATION_UNAVAILABLE") return formatTime(event.started_at);
  const range =
    event.ended_at && formatTime(event.ended_at) !== formatTime(event.started_at)
      ? `${formatTime(event.started_at)}-${formatTime(event.ended_at)}`
      : formatTime(event.started_at);
  return `${range} · ${event.checks} checks in a row`;
}

export default function IdentityReport({ identity }) {
  const status = identity.status ?? "not_verified";

  return (
    <section className="report-panel identity-report">
      <div className="identity-report__head">
        <div>
          <h2>Identity verification</h2>
          <p className="identity-report__method">
            {METHOD_LABELS[identity.method]} · {startResult(identity)}
          </p>
        </div>
        <span className={`identity-status identity-status--${status}`}>{STATUS_LABELS[status]}</span>
      </div>

      {identity.status_reason && <p className="identity-report__reason">{identity.status_reason}</p>}

      <dl className="identity-counts">
        {COUNTS.map(([key, label]) => (
          <div key={key} className="identity-counts__cell">
            <dt>{label}</dt>
            <dd>{identity[key]}</dd>
          </div>
        ))}
      </dl>

      {identity.events.length > 0 && (
        <>
          <p className="identity-report__subhead">Integrity events</p>
          <ul className="identity-events">
            {identity.events.map((event) => (
              <li key={`${event.type}-${event.started_at}`} className="identity-events__item">
                <span className="identity-events__label">{EVENT_LABELS[event.type] ?? event.type}</span>
                <span className="identity-events__meta">{eventMeta(event)}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="identity-report__privacy">
        Camera frames were analysed and discarded. The face reference used for this session was deleted
        when it ended.
      </p>
    </section>
  );
}
