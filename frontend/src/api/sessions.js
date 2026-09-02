import apiClient from "./client";

export async function createSession(role) {
  const { data } = await apiClient.post("/sessions", { role });
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
