import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import CameraPanel from "../components/CameraPanel";
import ConfirmDialog from "../components/ConfirmDialog";
import IdentityGate from "../components/IdentityGate";
import Notice from "../components/Notice";
import useAttentionChecks from "../hooks/useAttentionChecks";
import useAudioRecorder from "../hooks/useAudioRecorder";
import useCamera from "../hooks/useCamera";
import useIdentityChecks from "../hooks/useIdentityChecks";
import useInterviewerVoice from "../hooks/useInterviewerVoice";
import { endSession, getSession, submitConversationTurn } from "../api/sessions";
import { difficultyLabel } from "../constants/difficulty";
import { getRole } from "../constants/roles";
import { MIN_ANSWERED_FOR_HISTORY } from "../constants/session";
import "../components/AnswerRecorder.css";
import "./Interview.css";
import "./Conversation.css";

const TOTAL_QUESTIONS = 5;
// Long enough that a thinking pause mid-answer doesn't end the turn; the Done
// button is there for anyone who finishes sooner.
const END_OF_TURN_SILENCE_MS = 3000;
const SCORE_POLL_MS = 3000;
const BAR_COUNT = 32;

const STATUS_LABELS = {
  ready: "Ready when you are",
  speaking: "Speaking",
  listening: "Listening",
  processing: "Thinking",
  finishing: "Wrapping up",
};

function formatTime(totalSeconds) {
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const s = String(totalSeconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function lastInterviewerTurn(session) {
  return [...(session?.conversation?.turns ?? [])].reverse().find((t) => t.speaker === "interviewer");
}

/**
 * Copies scores from `other` into `base` wherever `base` doesn't have one yet.
 * Background scoring and turn responses race each other; neither should be
 * able to un-score a question the screen has already shown.
 */
function mergeScores(base, other) {
  if (!other) return base;
  let changed = false;
  const questions = base.questions.map((question, i) => {
    const candidate = other.questions[i];
    if (question.content_score != null || candidate?.content_score == null) return question;
    changed = true;
    return { ...question, ...candidate };
  });
  return changed ? { ...base, questions } : base;
}

export default function Conversation() {
  const navigate = useNavigate();
  const location = useLocation();

  const [session, setSession] = useState(location.state?.session ?? null);
  const [identity, setIdentity] = useState(location.state?.session?.identity ?? null);
  const [stage, setStageState] = useState("ready");
  const [started, setStarted] = useState(false);
  const [error, setError] = useState(null);
  const [retryTurn, setRetryTurn] = useState(null);
  const [pendingLeave, setPendingLeave] = useState(null);
  const [leaving, setLeaving] = useState(false);
  const [checksStopped, setChecksStopped] = useState(false);

  const camera = useCamera();
  const recorder = useAudioRecorder();
  const voice = useInterviewerVoice();

  // Once ended (finish or confirmed leave), navigation shouldn't re-prompt.
  const settledRef = useRef(false);
  // Set while ending, so no in-flight step speaks or listens again afterwards.
  const stoppedRef = useRef(false);
  const stageRef = useRef("ready");
  // Each speak-then-listen flow gets a number; starting another (Repeat)
  // retires the old one instead of letting both open the microphone.
  const flowRef = useRef(0);
  const finishTurnRef = useRef(null);
  const transcriptRef = useRef(null);

  const setStage = useCallback((next) => {
    stageRef.current = next;
    setStageState(next);
  }, []);

  const identityRequired = Boolean(identity?.required);
  const gatePending = identityRequired && identity.gate === "pending";
  const { lastCheck, paused: identityPaused } = useIdentityChecks({
    sessionId: session?.id,
    identity,
    camera,
    active:
      Boolean(session) &&
      identityRequired &&
      (identity.gate === "verified" || identity.gate === "unmatched") &&
      !checksStopped,
    onIdentity: setIdentity,
  });

  // Where the candidate is looking. Sampled more often than identity and kept
  // apart from it: a glance at a second screen says nothing about who's sitting
  // there, so it never touches the identity verdict.
  const { attention } = useAttentionChecks({
    sessionId: session?.id,
    camera,
    active: Boolean(session) && !checksStopped && !gatePending,
  });

  const autoStartedRef = useRef(false);
  const startCamera = camera.start;
  useEffect(() => {
    if (gatePending && !autoStartedRef.current) {
      autoStartedRef.current = true;
      startCamera();
    }
  }, [gatePending, startCamera]);

  useEffect(() => {
    if (!session) navigate("/setup", { replace: true });
    else if (session.mode !== "conversation") navigate("/interview", { replace: true, state: { session } });
  }, [session, navigate]);

  useEffect(() => {
    if (!session || settledRef.current) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [session]);

  // Answers are scored in the background once the interviewer moves on; poll
  // until each score lands so it can be shown.
  const sessionId = session?.id;
  const scoringPending = Boolean(
    session?.questions.some((q) => q.closed_at && q.content_score == null)
  );
  useEffect(() => {
    if (!scoringPending || !sessionId) return undefined;
    const timer = setInterval(async () => {
      try {
        const fresh = await getSession(sessionId);
        setSession((current) => mergeScores(current, fresh));
      } catch {
        // Try again on the next tick.
      }
    }, SCORE_POLL_MS);
    return () => clearInterval(timer);
  }, [scoringPending, sessionId]);

  const turnCount = session?.conversation?.turns.length ?? 0;
  useEffect(() => {
    const list = transcriptRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [turnCount]);

  const listen = async () => {
    setError(null);
    const ok = await recorder.start({
      silenceMs: END_OF_TURN_SILENCE_MS,
      onSilence: () => finishTurnRef.current?.(),
    });
    if (!ok) {
      setStage("ready");
      return;
    }
    camera.startSampling();
    setStage("listening");
  };

  const finish = async () => {
    stoppedRef.current = true;
    flowRef.current += 1;
    voice.cancel();
    recorder.cancel();
    camera.stopSampling();
    // No identity check may land while the backend finalises the verdict.
    setChecksStopped(true);
    setError(null);
    setStage("finishing");
    try {
      const ended = await endSession(session.id);
      settledRef.current = true;
      const answered = ended.questions.filter((q) => q.content_score != null).length;
      if (ended.status === "completed") {
        navigate("/report", { state: { sessionId: ended.id } });
      } else {
        navigate("/dashboard", {
          state: {
            notice: `Only ${answered} question${answered === 1 ? "" : "s"} answered, so this session wasn't saved.`,
          },
        });
      }
    } catch (err) {
      stoppedRef.current = false;
      setChecksStopped(false);
      setError(err.response?.data?.detail || "Could not finish the session.");
      setStage("ready");
    }
  };

  /** Speak an interviewer line, then hand the turn to the candidate (or wrap up). */
  const converse = async (text, closed) => {
    const flow = ++flowRef.current;
    setStage("speaking");
    await voice.speak(text);
    if (flow !== flowRef.current || stoppedRef.current) return;
    if (closed) {
      await finish();
      return;
    }
    await listen();
  };

  const submitTurn = async (recording, frames) => {
    setStage("processing");
    setError(null);
    setRetryTurn(null);
    try {
      const result = await submitConversationTurn(
        session.id,
        recording.blob,
        recording.extension,
        frames
      );
      setSession((previous) => mergeScores(result.session, previous));
      if (stoppedRef.current) return;
      await converse(result.interviewer_turn.text, result.closed);
    } catch (err) {
      if (stoppedRef.current) return;
      if (err.response?.status === 409) {
        try {
          const fresh = await getSession(session.id);
          setSession((previous) => mergeScores(fresh, previous));
        } catch {
          // Keep what's on screen.
        }
        setError(err.response.data?.detail || "The conversation moved on. Continue to pick up where it left off.");
      } else {
        setError(
          err.response?.data?.detail ||
            "ARIA couldn't respond just now. Check the backend and Ollama are running, then try again."
        );
        setRetryTurn(() => () => submitTurn(recording, frames));
      }
      setStage("ready");
    }
  };

  const finishTurn = async () => {
    if (stageRef.current !== "listening") return;
    setStage("processing");
    const recording = await recorder.stop();
    const frames = camera.stopSampling();
    if (!recording?.blob?.size) {
      await listen();
      return;
    }
    await submitTurn(recording, frames);
  };

  useEffect(() => {
    finishTurnRef.current = finishTurn;
  });

  const begin = async () => {
    setError(null);
    setRetryTurn(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser can't record audio. Try a current version of Chrome, Edge, Firefox or Safari.");
      return;
    }
    // Ask for the microphone before the interviewer speaks, not after.
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
    } catch (err) {
      setError(
        err.name === "NotAllowedError"
          ? "Microphone access is blocked. Allow it from the icon in your browser's address bar, then press Begin again."
          : "No microphone was found. Connect one, then press Begin again."
      );
      return;
    }
    setStarted(true);
    const last = lastInterviewerTurn(session);
    await converse(last.text, session.conversation.phase === "closed");
  };

  const repeatQuestion = () => {
    if (stageRef.current === "listening") {
      recorder.cancel();
      camera.stopSampling();
    }
    converse(lastInterviewerTurn(session).text, false);
  };

  const handleNavigateAttempt = (proceed) => {
    if (settledRef.current) {
      proceed();
      return;
    }
    setPendingLeave(() => proceed);
  };

  const confirmLeave = async () => {
    setLeaving(true);
    stoppedRef.current = true;
    flowRef.current += 1;
    voice.cancel();
    recorder.cancel();
    camera.stopSampling();
    setChecksStopped(true);
    try {
      await endSession(session.id);
    } catch {
      // Best-effort: a failed end-call must not trap the candidate on the page.
    }
    settledRef.current = true;
    setLeaving(false);
    const proceed = pendingLeave;
    setPendingLeave(null);
    proceed?.();
  };

  if (!session || session.mode !== "conversation") return null;

  const role = getRole(session.role);
  const conversation = session.conversation;
  const questions = session.questions;
  const currentIndex = conversation.phase === "questioning" ? questions.length - 1 : -1;
  const current = currentIndex >= 0 ? questions[currentIndex] : null;
  const interviewerTurn = lastInterviewerTurn(session);
  const answeredCount = new Set(
    conversation.turns
      .filter((t) => t.speaker === "candidate" && t.kind === "answer")
      .map((t) => t.question_index)
  ).size;
  const latestScoredIndex = questions.findLastIndex((q) => q.content_score != null);
  const latest = latestScoredIndex >= 0 ? questions[latestScoredIndex] : null;
  const nextDifficulty = questions[latestScoredIndex + 1]?.difficulty_level;

  const phaseLabel = {
    intro: "Introduction",
    questioning: `Question ${questions.length} of ${TOTAL_QUESTIONS}`,
    candidate_questions: "Your questions",
    closed: "Wrap-up",
  }[conversation.phase];

  return (
    <div className="interview-shell">
      <AppHeader backTo="/dashboard" backLabel="Dashboard" onNavigateAttempt={handleNavigateAttempt} />

      {gatePending ? (
        <IdentityGate
          sessionId={session.id}
          identity={identity}
          camera={camera}
          onIdentityChange={setIdentity}
        />
      ) : (
        <div className="interview-grid">
          <section className="interview-main">
            {identity?.warning && (
              <p className="identity-warning" role="status">
                <span className="identity-warning__dot" aria-hidden="true" />
                {identity.warning.message}
              </p>
            )}

            <div className="interview-meta">
              <span className="interview-chip interview-chip--role">{role.short}</span>
              <span className="interview-chip">{phaseLabel}</span>
              {current && (
                <span className="interview-chip interview-chip--difficulty">
                  {difficultyLabel(current.difficulty_level)}
                </span>
              )}
              {current?.topic && <span className="interview-chip">{current.topic}</span>}
            </div>

            <div className="conversation-stage">
              <span
                className={`interviewer-avatar${voice.speaking ? " interviewer-avatar--speaking" : ""}`}
                aria-hidden="true"
              >
                <span />
                <span />
                <span />
                <span />
                <span />
              </span>
              <div className="conversation-stage__body">
                <p className="conversation-stage__who">
                  ARIA · Interviewer
                  <span className={`conversation-stage__status conversation-stage__status--${stage}`}>
                    {STATUS_LABELS[stage]}
                  </span>
                </p>
                <p className="conversation-caption" aria-live="polite">
                  {interviewerTurn?.text}
                </p>
              </div>
            </div>

            {error && <Notice title="Something went wrong.">{error}</Notice>}

            {stage === "ready" && (
              <div className="turn-panel">
                {!started && (
                  <p className="turn-panel__lead">
                    ARIA will ask each question out loud and respond to what you say. Answer as you
                    would in a real interview, then pause for about three seconds — or press Done —
                    when you've finished.
                  </p>
                )}
                <div className="turn-panel__actions">
                  {retryTurn ? (
                    <>
                      <button type="button" className="turn-primary" onClick={() => retryTurn()}>
                        Try again
                      </button>
                      <button type="button" className="turn-secondary" onClick={begin}>
                        Answer again instead
                      </button>
                    </>
                  ) : (
                    <button type="button" className="turn-primary" onClick={begin}>
                      {started ? "Continue" : "Begin interview"}
                    </button>
                  )}
                </div>
                {!started && (
                  <p className="turn-panel__hint">Headphones help — ARIA's voice won't echo into your microphone.</p>
                )}
                {recorder.error && <p className="recorder__error">{recorder.error}</p>}
              </div>
            )}

            {stage === "speaking" && (
              <div className="turn-panel turn-panel--row">
                <p className="turn-panel__hint">
                  {voice.engine === "browser"
                    ? "Using your browser's voice — the local interviewer voice isn't available."
                    : "Your turn starts as soon as ARIA finishes."}
                </p>
                <button type="button" className="turn-secondary" onClick={voice.cancel}>
                  Skip
                </button>
              </div>
            )}

            {stage === "listening" && (
              <div className="turn-panel">
                <div className="recorder__live">
                  <span className="recorder__dot" aria-hidden="true" />
                  <span className="recorder__time">{formatTime(recorder.seconds)}</span>
                  <span className="recorder__status">
                    {recorder.heardSpeech
                      ? "Listening — pause for a few seconds when you're done"
                      : "Your turn — start whenever you're ready"}
                  </span>
                </div>

                <div className="recorder__wave" ref={recorder.levelTargetRef} aria-hidden="true">
                  {Array.from({ length: BAR_COUNT }).map((_, i) => {
                    const falloff = 1 - Math.abs(i - BAR_COUNT / 2) / (BAR_COUNT / 2);
                    return <span key={i} style={{ "--falloff": falloff.toFixed(3) }} />;
                  })}
                </div>

                <div className="turn-panel__actions">
                  <button type="button" className="turn-primary" onClick={() => finishTurnRef.current?.()}>
                    Done
                  </button>
                  <button type="button" className="turn-secondary" onClick={repeatQuestion}>
                    Repeat the question
                  </button>
                </div>
              </div>
            )}

            {(stage === "processing" || stage === "finishing") && (
              <div className="turn-panel turn-panel--row" role="status">
                <span className="turn-spinner" aria-hidden="true" />
                <p className="turn-panel__hint">
                  {stage === "finishing"
                    ? "Scoring your last answers and preparing your report…"
                    : "ARIA is listening back to what you said…"}
                </p>
              </div>
            )}

            {latest && (
              <div className="answer-result" key={latest.question_id}>
                <div className="answer-result__head">
                  <span className="answer-result__score">{Math.round(latest.content_score)}</span>
                  <span className="answer-result__label">
                    question {latestScoredIndex + 1}
                    {nextDifficulty != null && nextDifficulty !== latest.difficulty_level && (
                      <em> · next question {nextDifficulty > latest.difficulty_level ? "harder" : "easier"}</em>
                    )}
                  </span>
                </div>
                {latest.delivery_note && (
                  <p className="answer-result__delivery">
                    <span className="answer-result__delivery-score">{Math.round(latest.delivery_score)}</span>
                    delivery · {latest.delivery_note}
                  </p>
                )}
                {latest.visual_note && (
                  <p className="answer-result__delivery">
                    <span className="answer-result__delivery-score">{Math.round(latest.gaze_score)}</span>
                    eye contact · {latest.visual_note}
                  </p>
                )}
                <p className="answer-result__feedback">{latest.feedback_text}</p>
              </div>
            )}

            <div className="interview-controls">
              <button
                type="button"
                className="interview-finish"
                onClick={finish}
                disabled={stage === "finishing" || answeredCount === 0}
                title={answeredCount === 0 ? "Answer at least one question first" : undefined}
              >
                {conversation.phase === "closed" ? "See your report →" : "Finish early →"}
              </button>
            </div>
          </section>

          <aside className="interview-side">
            <CameraPanel
              camera={camera}
              recording={stage === "listening"}
              identity={identity}
              lastCheck={lastCheck}
              identityPaused={identityPaused}
              attention={attention}
            />

            <div className="interview-panel">
              <p className="interview-panel__label">Progress</p>
              <ol className="question-track">
                {questions.map((q, i) => {
                  const scoring = q.closed_at && q.content_score == null;
                  return (
                    <li
                      key={q.question_id}
                      className={`question-track__item${
                        q.content_score != null ? " question-track__item--done" : ""
                      }${i === currentIndex ? " question-track__item--current" : ""}`}
                    >
                      <span className="question-track__index">{i + 1}</span>
                      <span className="question-track__topic">{q.topic ?? "Question"}</span>
                      <span className="question-track__score" title={scoring ? "Scoring…" : undefined}>
                        {q.content_score != null ? Math.round(q.content_score) : scoring ? "…" : "—"}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </div>

            <div className="interview-panel">
              <p className="interview-panel__label">Conversation</p>
              <ol className="transcript" ref={transcriptRef}>
                {conversation.turns.map((turn) => (
                  <li key={turn.id} className={`transcript__turn transcript__turn--${turn.speaker}`}>
                    <span className="transcript__speaker">
                      {turn.speaker === "interviewer" ? "ARIA" : "You"}
                    </span>
                    <span className="transcript__text">{turn.text}</span>
                  </li>
                ))}
              </ol>
            </div>
          </aside>
        </div>
      )}

      <ConfirmDialog
        open={pendingLeave != null}
        title="Leave this interview?"
        confirmLabel={
          leaving
            ? "Leaving…"
            : answeredCount >= MIN_ANSWERED_FOR_HISTORY
              ? "Leave & save"
              : "Leave without saving"
        }
        cancelLabel="Keep going"
        tone={answeredCount >= MIN_ANSWERED_FOR_HISTORY ? "neutral" : "danger"}
        busy={leaving}
        onConfirm={confirmLeave}
        onCancel={() => setPendingLeave(null)}
      >
        {answeredCount >= MIN_ANSWERED_FOR_HISTORY ? (
          <p>
            You've answered <strong>{answeredCount} questions</strong>. Leaving now scores what you've
            said and saves this session to your history, but you won't be able to continue the
            conversation.
          </p>
        ) : (
          <p>
            You've answered <strong>{answeredCount === 0 ? "no questions" : "only 1 question"}</strong>.
            Sessions need at least {MIN_ANSWERED_FOR_HISTORY} answered questions to be saved, so
            leaving now won't add anything to your history.
          </p>
        )}
      </ConfirmDialog>
    </div>
  );
}
