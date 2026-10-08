import { Link } from "react-router-dom";
import AdaptiveDemo from "../components/AdaptiveDemo";
import {
  AdaptiveIcon,
  BrainIcon,
  CameraIcon,
  EyeIcon,
  IconChip,
  MicIcon,
  PolicyIcon,
  ResumeIcon,
  ScoreIcon,
  ShieldIcon,
  TrendIcon,
} from "../components/FeatureIcons";
import Logo from "../components/Logo";
import Reveal from "../components/Reveal";
import "./Landing.css";

const FEATURES = [
  {
    icon: ResumeIcon,
    tint: "accent",
    title: "Personalised from your resume",
    body: "Upload it once and ARIA infers your role, seniority, and skills, then grounds its questions in your actual background instead of a generic bank.",
  },
  {
    icon: AdaptiveIcon,
    tint: "signal",
    title: "Difficulty that adapts as you go",
    body: "A policy trained on interview performance raises or lowers the next question after every answer, so you're consistently working near the edge of what you can do.",
  },
  {
    icon: ScoreIcon,
    tint: "accent",
    title: "Scored on content and delivery",
    body: "Correctness, depth, relevance, and clarity are graded from what you said. Separately, your pace, pauses, and filler words are measured from how you said it.",
  },
  {
    icon: EyeIcon,
    tint: "signal",
    title: "Optional visual feedback",
    body: "Turn on your camera for eye contact, engagement, and posture. Frames are analysed and discarded - never stored, never uploaded.",
  },
  {
    icon: ShieldIcon,
    tint: "accent",
    title: "Runs on your machine",
    body: "Speech recognition, scoring, and visual analysis all run locally. No API keys, no third-party upload, no per-interview cost.",
  },
  {
    icon: TrendIcon,
    tint: "signal",
    title: "Progress across sessions",
    body: "Every interview is saved. Track your score trend, your practice streak, and where you're improving over time.",
  },
];

const STATS = [
  { value: "5", label: "Scored questions per session", hint: "Each graded on its own, live" },
  { value: "4", label: "Rubric dimensions per answer", hint: "Correctness, depth, relevance, clarity" },
  { value: "3", label: "Delivery signals from your voice", hint: "Pace, pauses, filler words" },
  { value: "$0", label: "Cost per interview", hint: "Every model runs on your machine" },
];

const STACK = [
  {
    icon: MicIcon,
    tint: "signal",
    title: "Speech recognition",
    body: "Whisper transcribes your spoken answer locally, with word-level timing - the same timing that pace and pause measurements are computed from.",
  },
  {
    icon: BrainIcon,
    tint: "accent",
    title: "Question & scoring engine",
    body: "A local LLM generates role-specific questions grounded in your resume, and grades each transcribed answer against a four-part rubric in the same pass.",
  },
  {
    icon: PolicyIcon,
    tint: "signal",
    title: "Adaptive difficulty",
    body: "A Q-learning policy picks the next question's difficulty from your last few scores, aiming to keep you stretched rather than coasting or stuck.",
  },
  {
    icon: CameraIcon,
    tint: "accent",
    title: "Visual analysis",
    body: "When the camera is on, sampled frames are read locally for head orientation and expression, producing eye-contact and engagement scores.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Upload your resume",
    body: "Skills, role, and seniority are inferred automatically - required before your first session so questions are grounded in your background.",
  },
  {
    n: "02",
    title: "Choose a role and difficulty",
    body: "Practise a software engineering or HR/behavioural interview, pre-selected from your resume. Start at Auto, or pick your own starting difficulty.",
  },
  {
    n: "03",
    title: "Answer out loud",
    body: "Speak naturally into your microphone. A camera is optional, and typing remains available.",
  },
  {
    n: "04",
    title: "Review your report",
    body: "A rubric breakdown, a per-question speaking-pace grid, and specific strengths and gaps to work on next.",
  },
];

export default function Landing() {
  const scrollTo = (e, id) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="landing-nav__mark">
          <Logo size={24} />
          <span>ARIA</span>
        </div>
        <nav className="landing-nav__links" aria-label="Page sections">
          <a href="#features" onClick={(e) => scrollTo(e, "features")}>
            Features
          </a>
          <a href="#technology" onClick={(e) => scrollTo(e, "technology")}>
            Technology
          </a>
          <a href="#how-it-works" onClick={(e) => scrollTo(e, "how-it-works")}>
            How it works
          </a>
        </nav>
        <div className="landing-nav__actions">
          <Link to="/login" className="landing-nav__login">
            Log in
          </Link>
          <Link to="/signup" className="landing-nav__signup">
            Get started
          </Link>
        </div>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-hero__copy">
            <p className="landing-eyebrow">Interview practice, measured properly</p>
            <h1 className="landing-hero__headline">
              Practice interviews that <span className="gradient-text">adapt</span> to how
              you're actually performing.
            </h1>
            <p className="landing-hero__sub">
              ARIA runs a full mock interview - voice, and camera if you choose - then scores
              what you said and how you said it. The difficulty adjusts to you in real time, and
              everything runs on your own device.
            </p>
            <div className="landing-hero__actions">
              <Link to="/signup" className="landing-cta">
                Create a free account
              </Link>
              <Link to="/login" className="landing-cta landing-cta--ghost">
                Log in
              </Link>
            </div>
          </div>

          <div className="landing-hero__visual" aria-hidden="true">
            <div className="hero-card">
              <div className="hero-card__row">
                <span className="hero-card__label">Question 3 of 5</span>
                <span className="hero-card__badge">Moderate</span>
              </div>
              <p className="hero-card__question">
                How would you cache the results of an expensive database query in a web
                application?
              </p>
              <div className="hero-card__meter">
                <div className="hero-card__meter-row">
                  <span>Correctness</span>
                  <span className="hero-card__bar">
                    <span style={{ width: "82%" }} />
                  </span>
                </div>
                <div className="hero-card__meter-row">
                  <span>Clarity</span>
                  <span className="hero-card__bar">
                    <span style={{ width: "68%" }} />
                  </span>
                </div>
                <div className="hero-card__meter-row">
                  <span>Pace</span>
                  <span className="hero-card__bar">
                    <span style={{ width: "91%" }} />
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <Reveal as="section" className="landing-trust">
          <p>
            No API keys. No account with a third-party model provider. Speech-to-text, question
            scoring, and visual analysis are all performed by models running locally - nothing
            you say or show is sent off your machine.
          </p>
        </Reveal>

        <section className="landing-section landing-section--stats">
          <div className="landing-stats">
            {STATS.map((s, i) => (
              <Reveal key={s.label} className="landing-stat" delay={i * 60}>
                <p className="landing-stat__value gradient-text">{s.value}</p>
                <p className="landing-stat__label">{s.label}</p>
                <p className="landing-stat__hint">{s.hint}</p>
              </Reveal>
            ))}
          </div>
        </section>

        <section id="features" className="landing-section">
          <Reveal>
            <p className="landing-eyebrow">Features</p>
            <h2 className="landing-section__title">Built as a complete assessment, not a quiz.</h2>
          </Reveal>

          <div className="landing-features">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} className="landing-feature" delay={i * 60}>
                <IconChip tint={f.tint}>
                  <f.icon />
                </IconChip>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </Reveal>
            ))}
          </div>
        </section>

        <section id="technology" className="landing-section landing-section--tinted">
          <Reveal>
            <p className="landing-eyebrow">Under the hood</p>
            <h2 className="landing-section__title">Four engines, all running on your machine.</h2>
            <p className="landing-section__sub">
              No cloud inference, no per-token billing. This is what actually runs when you take
              a mock interview.
            </p>
          </Reveal>

          <div className="landing-features landing-features--stack">
            {STACK.map((s, i) => (
              <Reveal key={s.title} className="landing-feature" delay={i * 60}>
                <IconChip tint={s.tint}>
                  <s.icon />
                </IconChip>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </Reveal>
            ))}
          </div>
        </section>

        <section id="how-it-works" className="landing-section">
          <Reveal>
            <p className="landing-eyebrow">How it works</p>
            <h2 className="landing-section__title">From resume to report in four steps.</h2>
          </Reveal>

          <ol className="landing-steps">
            {STEPS.map((s, i) => (
              <Reveal as="li" key={s.n} className="landing-step" delay={i * 60}>
                <span className="landing-step__n gradient-text">{s.n}</span>
                <div>
                  <h3>{s.title}</h3>
                  <p>{s.body}</p>
                </div>
              </Reveal>
            ))}
          </ol>
        </section>

        <section className="landing-section landing-section--demo landing-section--tinted">
          <Reveal>
            <p className="landing-eyebrow">See it adapt</p>
            <h2 className="landing-section__title">
              The next question depends on your last few answers.
            </h2>
            <p className="landing-section__sub">
              A policy trained during practice sessions decides whether to raise or lower the
              difficulty - not a fixed script. Try both states below.
            </p>
          </Reveal>

          <Reveal delay={100}>
            <AdaptiveDemo />
          </Reveal>
        </section>

        <Reveal as="section" className="landing-final">
          <h2>Ready to see how you actually come across?</h2>
          <Link to="/signup" className="landing-cta">
            Create a free account
          </Link>
        </Reveal>
      </main>

      <footer className="landing-footer">
        <div className="landing-nav__mark">
          <Logo size={20} />
          <span>ARIA</span>
        </div>
        <p>Adaptive Real-Time Interview Assessment.</p>
        <div className="landing-footer__links">
          <Link to="/login">Log in</Link>
          <Link to="/signup">Sign up</Link>
        </div>
      </footer>
    </div>
  );
}
