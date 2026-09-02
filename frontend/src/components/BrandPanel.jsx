import Logo from "./Logo";
import "./BrandPanel.css";

const FEATURES = [
  "Adaptive question difficulty",
  "Real-time speech & visual feedback",
  "Progress tracked across sessions",
];

const BAR_COUNT = 24;

export default function BrandPanel() {
  return (
    <aside className="brand-panel">
      <div className="brand-panel__glow" aria-hidden="true" />
      <div className="brand-panel__grid" aria-hidden="true" />

      <div className="brand-panel__content">
        <div className="brand-panel__mark">
          <Logo size={28} />
          <span>ARIA</span>
        </div>

        <h1 className="brand-panel__headline">
          Practice interviews that <span>adapt to you.</span>
        </h1>
        <p className="brand-panel__sub">
          Role-specific mock interviews, scored in real time on what you said and how you said
          it — so you walk into the real one ready.
        </p>

        <ul className="brand-panel__features">
          {FEATURES.map((f) => (
            <li key={f}>
              <span className="brand-panel__dot" />
              {f}
            </li>
          ))}
        </ul>
      </div>

      <div className="brand-panel__waveform" aria-hidden="true">
        {Array.from({ length: BAR_COUNT }).map((_, i) => (
          <span key={i} style={{ animationDelay: `${(i % 8) * 90}ms` }} />
        ))}
      </div>
    </aside>
  );
}
