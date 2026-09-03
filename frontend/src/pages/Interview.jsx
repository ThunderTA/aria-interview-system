import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import AnswerRecorder from "../components/AnswerRecorder";
import AppHeader from "../components/AppHeader";
import Notice from "../components/Notice";
import ScoringProgress from "../components/ScoringProgress";
import {
  currentQuestionIndex,
  endSession,
  fetchNextQuestion,
  submitAnswer,
  submitSpokenAnswer,
} from "../api/sessions";
import { getRole } from "../constants/roles";
import "./Interview.css";

const DIFFICULTY_LABELS = { 1: "Warm-up", 2: "Easy", 3: "Moderate", 4: "Challenging", 5: "Hard" };
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

  // Reached directly without going through Setup — there's no session to run.
  useEffect(() => {
    if (!session) navigate("/setup", { replace: true });
  }, [session, navigate]);

  if (!session) return null;

  const role = getRole(session.role);
  const index = currentQuestionIndex(session);
  const question = index >= 0 ? session.questions[index] : null;
  const answeredCount = session.questions.filter((q) => q.content_score != null).length;
  const isLastAnswered = index < 0;
  // Most recent answer that carried delivery metrics, i.e. was spoken.
  const lastSpoken = [...session.questions].reverse().find((q) => q.wpm != null);

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

  const handleSpokenAnswer = (blob, extension) =>
    runSubmission(() => submitSpokenAnswer(session.id, blob, extension));

  const handleTypedAnswer = (text) =>
    runSubmission(() => submitAnswer(session.id, text));

  const handleFinish = async () => {
    setScoring(true);
    try {
      const ended = await endSession(session.id);
      navigate("/report", { state: { sessionId: ended.id } });
    } catch (err) {
      setError(err.response?.data?.detail || "Could not finish the session.");
      setScoring(false);
    }
  };

  return (
    <div className="interview-shell">
      <AppHeader backTo="/dashboard" backLabel="Dashboard" />

      <div className="interview-grid">
        <section className="interview-main">
          <div className="interview-meta">
            <span className="interview-chip interview-chip--role">{role.short}</span>
            <span className="interview-chip">
              Question {Math.min(answeredCount + 1, session.questions.length)} of{" "}
              {isLastAnswered ? answeredCount : 5}
            </span>
            {question && (
              <span className="interview-chip interview-chip--difficulty">
                {DIFFICULTY_LABELS[question.difficulty_level] ?? "Moderate"}
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
                <span className="signal-list__value">—</span>
              </li>
            </ul>
            <p className="interview-panel__hint">
              {lastSpoken
                ? "Eye contact and posture arrive with the camera milestone."
                : "Speak your answer to see pace, pauses and filler words measured here."}
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
