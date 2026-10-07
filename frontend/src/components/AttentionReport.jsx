import { ATTENTION_LABELS } from "../constants/attention";

// Everything that isn't "looking at the camera", in the order it reads best.
const AWAY_ORDER = ["looking_down", "looking_left", "looking_right", "looking_up", "turned_away", "eyes_closed", "no_face"];

function formatTime(value) {
  return new Date(value).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** Where the candidate looked across the whole interview. */
export default function AttentionReport({ attention }) {
  const onCamera = attention.on_camera_share;
  const away = AWAY_ORDER.filter((state) => attention.shares[state] > 0).map((state) => ({
    state,
    share: attention.shares[state],
  }));

  return (
    <section className="report-panel attention-report">
      <div className="identity-report__head">
        <div>
          <h2>Attention &amp; gaze</h2>
          <p className="identity-report__method">
            {attention.checks} camera checks during the interview
          </p>
        </div>
        <span className="attention-share">{Math.round(onCamera)}% eye contact</span>
      </div>

      <div className="attention-bar" role="img" aria-label={`${Math.round(onCamera)} percent looking at the camera`}>
        <span className="attention-bar__fill attention-bar__fill--on" style={{ width: `${onCamera}%` }} />
        {away.map(({ state, share }) => (
          <span
            key={state}
            className={`attention-bar__fill attention-bar__fill--${state}`}
            style={{ width: `${share}%` }}
            title={`${ATTENTION_LABELS[state]} — ${Math.round(share)}%`}
          />
        ))}
      </div>

      <ul className="attention-legend">
        <li>
          <span className="attention-legend__swatch attention-legend__swatch--on" aria-hidden="true" />
          Looking at the camera <strong>{Math.round(onCamera)}%</strong>
        </li>
        {away.map(({ state, share }) => (
          <li key={state}>
            <span
              className={`attention-legend__swatch attention-legend__swatch--${state}`}
              aria-hidden="true"
            />
            {ATTENTION_LABELS[state]} <strong>{Math.round(share)}%</strong>
          </li>
        ))}
      </ul>

      {attention.note && <p className="identity-report__reason">{attention.note}</p>}

      {attention.episodes.length > 0 && (
        <>
          <p className="identity-report__subhead">Sustained spells away from the camera</p>
          <ul className="identity-events">
            {attention.episodes.map((episode) => (
              <li key={`${episode.state}-${episode.started_at}`} className="identity-events__item attention-events__item">
                <span className="attention-events__label">{episode.label}</span>
                <span className="identity-events__meta">
                  {Math.round(episode.seconds)}s
                  {episode.started_at && ` · from ${formatTime(episode.started_at)}`}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="identity-report__privacy">
        Where you looked is worked out from head position and eye direction in sampled frames, which
        are analysed and discarded. It describes what the camera saw, not why.
      </p>
    </section>
  );
}
