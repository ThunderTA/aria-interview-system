import apiClient from "./client";

export async function createSession(role, startingDifficulty = null, mode = "classic", voice = null) {
  const { data } = await apiClient.post("/sessions", {
    role,
    starting_difficulty: startingDifficulty,
    mode,
    voice,
  });
  return data;
}

/** The report as a PDF, built on request. Returns the blob and its filename. */
export async function downloadReportPdf(sessionId) {
  const response = await apiClient.get(`/sessions/${sessionId}/report/pdf`, {
    responseType: "blob",
    timeout: 60000,
  });
  const match = /filename="([^"]+)"/.exec(response.headers["content-disposition"] ?? "");
  return { blob: response.data, filename: match?.[1] ?? `aria-report-${sessionId}.pdf` };
}

export async function getSession(sessionId) {
  const { data } = await apiClient.get(`/sessions/${sessionId}`);
  return data;
}

/** One spoken turn in a conversational interview; resolves with the interviewer's reply. */
export async function submitConversationTurn(sessionId, blob, extension = "webm", frames = []) {
  const form = new FormData();
  form.append("audio", blob, `turn.${extension}`);
  frames.forEach((frame, i) => form.append("frames", frame, `frame-${i}.jpg`));
  // Transcription plus the interviewer's reply - and the next question, when
  // the interviewer moves on - all on local models.
  const { data } = await apiClient.post(`/sessions/${sessionId}/conversation/turn`, form, {
    timeout: 180000,
  });
  return data;
}

export async function submitAnswer(sessionId, transcript) {
  // Scoring runs on a local LLM and can take ~30s, so this call overrides the
  // client's default timeout.
  const { data } = await apiClient.post(
    `/sessions/${sessionId}/answer`,
    { transcript },
    { timeout: 180000 }
  );
  return data;
}

export async function submitSpokenAnswer(sessionId, blob, extension = "webm", frames = []) {
  const form = new FormData();
  form.append("audio", blob, `answer.${extension}`);
  frames.forEach((frame, i) => form.append("frames", frame, `frame-${i}.jpg`));
  // Transcription plus scoring on a local model; same generous ceiling as text.
  const { data } = await apiClient.post(`/sessions/${sessionId}/answer/audio`, form, {
    timeout: 240000,
  });
  return data;
}

/** Start-of-interview identity check on a short burst of webcam frames. */
export async function verifyIdentity(sessionId, frames, { continueUnmatched = false } = {}) {
  const form = new FormData();
  frames.forEach((frame, i) => form.append("frames", frame, `start-${i}.jpg`));
  if (continueUnmatched) form.append("continue_unmatched", "true");
  const { data } = await apiClient.post(`/sessions/${sessionId}/identity/verify`, form, {
    timeout: 60000,
  });
  return data;
}

/** Proceed without verification - the backend only allows it while face analysis can't run. */
export async function skipIdentity(sessionId) {
  const { data } = await apiClient.post(`/sessions/${sessionId}/identity/skip`);
  return data;
}

/** One periodic check. A null frame reports that the camera is off. */
export async function checkIdentity(sessionId, frame) {
  const form = new FormData();
  if (frame) {
    form.append("frame", frame, "check.jpg");
  } else {
    form.append("camera_off", "true");
  }
  const { data } = await apiClient.post(`/sessions/${sessionId}/identity/check`, form, {
    timeout: 30000,
  });
  return data;
}

/** One frame for the live attention readout: where the candidate is looking. */
export async function checkAttention(sessionId, frame) {
  const form = new FormData();
  form.append("frame", frame, "attention.jpg");
  const { data } = await apiClient.post(`/sessions/${sessionId}/attention/check`, form, {
    timeout: 20000,
  });
  return data;
}

export async function fetchNextQuestion(sessionId) {
  const { data } = await apiClient.post(`/sessions/${sessionId}/next`, null, { timeout: 180000 });
  return data;
}

export async function endSession(sessionId) {
  const { data } = await apiClient.post(`/sessions/${sessionId}/end`, null, { timeout: 60000 });
  return data;
}

export async function getReport(sessionId) {
  const { data } = await apiClient.get(`/sessions/${sessionId}/report`);
  return data;
}

export async function listSessions() {
  const { data } = await apiClient.get("/sessions");
  return data;
}

/** Index of the question currently awaiting an answer, or -1 if none. */
export function currentQuestionIndex(session) {
  return session.questions.findIndex((q) => q.content_score === null || q.content_score === undefined);
}
