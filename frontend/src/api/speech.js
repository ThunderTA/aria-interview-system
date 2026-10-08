import apiClient from "./client";

/** WAV audio of `text` in the interviewer's voice, synthesised on the backend. */
export async function synthesizeSpeech(text, { voice, signal } = {}) {
  const { data } = await apiClient.post(
    "/speech",
    { text, voice },
    { responseType: "blob", signal, timeout: 30000 }
  );
  return data;
}

/** The interviewer voices a candidate can pick from, for the Setup preview. */
export async function fetchVoices() {
  const { data } = await apiClient.get("/speech/voices");
  return data;
}
