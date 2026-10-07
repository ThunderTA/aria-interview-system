import apiClient from "./client";

/** WAV audio of `text` in the interviewer's voice, synthesised on the backend. */
export async function synthesizeSpeech(text, { signal } = {}) {
  const { data } = await apiClient.post(
    "/speech",
    { text },
    { responseType: "blob", signal, timeout: 30000 }
  );
  return data;
}
