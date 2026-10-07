import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import AnswerRecorder from "../components/AnswerRecorder";
import AppHeader from "../components/AppHeader";
import CameraPanel from "../components/CameraPanel";
import ConfirmDialog from "../components/ConfirmDialog";
import IdentityGate from "../components/IdentityGate";
import Notice from "../components/Notice";
import ScoringProgress from "../components/ScoringProgress";
import useAttentionChecks from "../hooks/useAttentionChecks";
import useCamera from "../hooks/useCamera";
import useIdentityChecks from "../hooks/useIdentityChecks";
import {
  currentQuestionIndex,
  endSession,
  fetchNextQuestion,
  submitAnswer,
  submitSpokenAnswer,
} from "../api/sessions";
import { difficultyLabel } from "../constants/difficulty";
import { getRole } from "../constants/roles";
import { MIN_ANSWERED_FOR_HISTORY } from "../constants/session";
import "./Interview.css";

const TOTAL_QUESTIONS = 5;

export default function Interview() {
  const navigate = useNavigate();
  const location = useLocation();

  const [session, setSession] = useState(location.state?.session ?? null);
  const [scoring, setScoring] = useState(false);
  const [loadingNext, setLoadingNext] = useState(false);
  const [error, setError] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [lastSubmissionWasSpoken, setLastSubmissionWasSpoken] = useState(false);
  const [answering, setAnswering] = useState(false);
  // Holds the "actually navigate now" callback while the leave-confirmation
  // is open; null means the dialog is closed.
  const [pendingLeave, setPendingLeave] = useState(null);
  const [leaving, setLeaving] = useState(false);
  const camera = useCamera();
  // Once the session has been explicitly ended (finish, or a confirmed
  // leave), further navigation shouldn't re-prompt — it's already settled.
  const settledRef = useRef(false);

  // Kept apart from `session`: answer responses carry an identity snapshot
  // from when scoring started, which a check may have superseded since.
  const [identity, setIdentity] = useState(location.state?.session?.identity ?? null);
  const [checksStopped, setChecksStopped] = useState(false);
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

  // The camera is required when identity is verified, so ask straight away
  // rather than making the candidate find a button first.
  const autoStartedRef = useRef(false);
  const startCamera = camera.start;
  useEffect(() => {
    if (gatePending && !autoStartedRef.current) {
      autoStartedRef.current = true;
      startCamera();
    }
  }, [gatePending, startCamera]);

  // Reached directly without going through Setup — there's no session to run.
  useEffect(() => {
    if (!session) navigate("/setup", { replace: true });
  }, [session, navigate]);

  // A native prompt as a backstop for tab close/refresh/typed-URL navigation,
  // which in-app navigation guarding can't intercept. Browsers show their own
  // generic text regardless of what's set here — that's a platform security
  // restriction, not something stylable.
  useEffect(() => {
    if (!session || settledRef.current) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [session]);

  if (!session) return null;

  const role = getRole(session.role);
  const index = currentQuestionIndex(session);
  const question = index >= 0 ? session.questions[index] : null;
  const answeredCount = session.questions.filter((q) => q.content_score != null).length;
  const isLastAnswered = index < 0;

  /** Every AppHeader-triggered navigation (logo, back link, logout) comes through here. */
  const handleNavigateAttempt = (proceed) => {
    if (settledRef.current) {
      proceed();
      return;
    }
    setPendingLeave(() => proceed);
  };

  const confirmLeave = async () => {
    setLeaving(true);
    setChecksStopped(true);
    try {
      await endSession(session.id);
    } catch {
      // Best-effort: a failed end-call must not trap the candidate on the
      // page — they're already trying to leave.
    }
    settledRef.current = true;
    setLeaving(false);
    const proceed = pendingLeave;
    setPendingLeave(null);
    proceed?.();
  };
  // Most recent answer that carried delivery metrics, i.e. was spoken.
  const lastSpoken = [...session.questions].reverse().find((q) => q.wpm != null);
  const lastVisual = [...session.questions].reverse().find((q) => q.gaze_score != null);

  /** Runs an answer through scoring, then queues the next question. */
  const runSubmission = async (submit) => {
    if (scoring) return;
    setScoring(true);
    setError(null);
    try {
      const scoredSession = await submit();
      const justScored = scoredSession.questions[index];

      // Show the score and feedback straight away — there's something to read
      // while the next question is still being generated.
      setLastResult({
        score: justScored.content_score,
        feedback: justScored.feedback_text,
        transcript: justScored.transcript,
        deliveryScore: justScored.delivery_score,
        deliveryNote: justScored.delivery_note,
        visualNote: justScored.visual_note,
        gazeScore: justScored.gaze_score,
        previousDifficulty: justScored.difficulty_level,
        nextDifficulty: null,
      });
      setSession(scoredSession);
      setScoring(false);

      if (scoredSession.questions.length < TOTAL_QUESTIONS) {
        setLoadingNext(true);
        try {
          const withNext = await fetchNextQuestion(session.id);
          const upcoming = withNext.questions[currentQuestionIndex(withNext)];
          setSession(withNext);
          setLastResult((prev) =>
            prev ? { ...prev, nextDifficulty: upcoming?.difficulty_level ?? null } : prev
          );
        } catch (err) {
          setError(
            err.response?.data?.detail ||
              "Your answer was scored, but the next question couldn't be generated."
          );
        } finally {
          setLoadingNext(false);
        }
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Scoring failed. Your answer wasn't recorded.");
      setScoring(false);
    }
  };

  const handleSpokenAnswer = (blob, extension) => {
    const frames = camera.stopSampling();
    setAnswering(false);
    return runSubmission(() => submitSpokenAnswer(session.id, blob, extension, frames));
  };

  const handleTypedAnswer = (text) =>
    runSubmission(() => submitAnswer(session.id, text));

  const handleFinish = async () => {
    setScoring(true);
    // No check may land while the backend is finalising the identity verdict.
    setChecksStopped(true);
    try {
      const ended = await endSession(session.id);
      settledRef.current = true;
      if (ended.status === "completed") {
        navigate("/report", { state: { sessionId: ended.id } });
      } else {
        // Fewer than MIN_ANSWERED_FOR_HISTORY questions were answered — the
        // backend discarded it rather than creating a near-empty report.
        navigate("/dashboard", {
          state: { notice: `Only ${answeredCount} question${answeredCount === 1 ? "" : "s"} answered, so this session wasn't saved.` },
        });
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Could not finish the session.");
      setScoring(false);
      setChecksStopped(false);
    }
  };

  return (
    <div className="interview-shell">
      <AppHeader
        backTo="/dashboard"
        backLabel="Dashboard"
        onNavigateAttempt={handleNavigateAttempt}
      />

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
              <span className="interview-chip">
                Question {Math.min(answeredCount + 1, session.questions.length)} of{" "}
                {isLastAnswered ? answeredCount : 5}
              </span>
              {question && (
                <span className="interview-chip interview-chip--difficulty">
                  {difficultyLabel(question.difficulty_level)}
                </span>
              )}
              {question?.topic && <span className="interview-chip">{question.topic}</span>}
            </div>

            {loadingNext ? (
              <h1 className="interview-question interview-question--pending">
                Preparing your next question<span className="dots" aria-hidden="true" />
              </h1>
            ) : isLastAnswered ? (
              <div className="interview-complete">
                <h1 className="interview-question">
                  {answeredCount >= TOTAL_QUESTIONS
                    ? `That's all ${answeredCount} questions.`
                    : `${answeredCount} answered.`}
                </h1>
                <p>Finish up to see your scored report.</p>
              </div>
            ) : (
              <h1 className="interview-question">{question.text}</h1>
            )}

            {lastResult && !scoring && (
              <div className="answer-result">
                <div className="answer-result__head">
                  <span className="answer-result__score">{lastResult.score}</span>
                  <span className="answer-result__label">
                    previous answer
                    {lastResult.nextDifficulty != null &&
                      lastResult.nextDifficulty !== lastResult.previousDifficulty && (
                        <em>
                          {" "}
                          · next question{" "}
                          {lastResult.nextDifficulty > lastResult.previousDifficulty
                            ? "harder"
                            : "easier"}
                        </em>
                      )}
                  </span>
                </div>

                {lastResult.deliveryNote && (
                  <p className="answer-result__delivery">
                    <span className="answer-result__delivery-score">
                      {Math.round(lastResult.deliveryScore)}
                    </span>
                    delivery · {lastResult.deliveryNote}
                  </p>
                )}

                {lastResult.visualNote && (
                  <p className="answer-result__delivery">
                    <span className="answer-result__delivery-score">
                      {Math.round(lastResult.gazeScore)}
                    </span>
                    eye contact · {lastResult.visualNote}
                  </p>
                )}

                <p className="answer-result__feedback">{lastResult.feedback}</p>

                {lastResult.transcript && (
                  <details className="answer-result__transcript">
                    {/* Candidates should be able to check what was actually heard —
                        a mis-transcription would otherwise look like a bad score. */}
                    <summary>What ARIA heard</summary>
                    <p>{lastResult.transcript}</p>
                  </details>
                )}
              </div>
            )}

            {error && <Notice title="Something went wrong.">{error}</Notice>}

            {scoring ? (
              <ScoringProgress spoken={lastSubmissionWasSpoken} />
            ) : (
              !isLastAnswered &&
              !loadingNext && (
                <AnswerRecorder
                  key={question.question_id}
                  onStart={() => {
                    setAnswering(true);
                    camera.startSampling();
                  }}
                  onDiscard={() => {
                    setAnswering(false);
                    camera.stopSampling();
                  }}
                  onSubmitAudio={(blob, ext) => {
                    setLastSubmissionWasSpoken(true);
                    handleSpokenAnswer(blob, ext);
                  }}
                  onSubmitText={(text) => {
                    setLastSubmissionWasSpoken(false);
                    handleTypedAnswer(text);
                  }}
                  disabled={scoring}
                />
              )
            )}

            <div className="interview-controls">
              <button
                type="button"
                className="interview-finish"
                onClick={handleFinish}
                disabled={scoring || answeredCount === 0}
                title={answeredCount === 0 ? "Answer at least one question first" : undefined}
              >
                {isLastAnswered ? "See your report →" : "Finish early →"}
              </button>
            </div>
          </section>

          <aside className="interview-side">
            <CameraPanel
              camera={camera}
              recording={answering}
              identity={identity}
              lastCheck={lastCheck}
              identityPaused={identityPaused}
              attention={attention}
            />

            <div className="interview-panel">
              <p className="interview-panel__label">Progress</p>
              <ol className="question-track">
                {session.questions.map((q, i) => (
                  <li
                    key={q.question_id}
                    className={`question-track__item${
                      q.content_score != null ? " question-track__item--done" : ""
                    }${i === index ? " question-track__item--current" : ""}`}
                  >
                    <span className="question-track__index">{i + 1}</span>
                    <span className="question-track__topic">{q.topic ?? "Question"}</span>
                    <span className="question-track__score">
                      {q.content_score != null ? Math.round(q.content_score) : "—"}
                    </span>
                  </li>
                ))}
              </ol>
            </div>

            <div className="interview-panel">
              <p className="interview-panel__label">Last answer</p>
              <ul className="signal-list">
                <li>
                  <span>Speaking pace</span>
                  <span className="signal-list__value">
                    {lastSpoken?.wpm != null ? `${Math.round(lastSpoken.wpm)} wpm` : "—"}
                  </span>
                </li>
                <li>
                  <span>Filler words</span>
                  <span className="signal-list__value">
                    {lastSpoken?.filler_count != null ? lastSpoken.filler_count : "—"}
                  </span>
                </li>
                <li>
                  <span>Long pauses</span>
                  <span className="signal-list__value">
                    {lastSpoken?.pause_count != null ? lastSpoken.pause_count : "—"}
                  </span>
                </li>
                <li>
                  <span>Eye contact</span>
                  <span className="signal-list__value">
                    {lastVisual?.gaze_score != null ? `${Math.round(lastVisual.gaze_score)}%` : "—"}
                  </span>
                </li>
                <li>
                  <span>Posture</span>
                  <span className="signal-list__value">
                    {lastVisual?.posture_score != null
                      ? Math.round(lastVisual.posture_score)
                      : "—"}
                  </span>
                </li>
              </ul>
              <p className="interview-panel__hint">
                {!lastSpoken
                  ? "Speak your answer to see pace, pauses and filler words measured here."
                  : !lastVisual
                    ? "Turn the camera on to add eye contact and posture."
                    : "Measured from your last answer."}
              </p>
            </div>
          </aside>
        </div>
      )}

      <ConfirmDialog
        open={pendingLeave != null}
        title="Leave this interview?"
        confirmLabel={
          leaving ? "Leaving…" : answeredCount >= MIN_ANSWERED_FOR_HISTORY ? "Leave & save" : "Leave without saving"
        }
        cancelLabel="Keep going"
        tone={answeredCount >= MIN_ANSWERED_FOR_HISTORY ? "neutral" : "danger"}
        busy={leaving}
        onConfirm={confirmLeave}
        onCancel={() => setPendingLeave(null)}
      >
        {answeredCount >= MIN_ANSWERED_FOR_HISTORY ? (
          <p>
            You've answered <strong>{answeredCount} questions</strong>. Leaving now saves this
            session to your history — you can review the report anytime, but you won't be able to
            continue answering.
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
