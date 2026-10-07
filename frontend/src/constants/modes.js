// ids must match SessionMode in backend/app/models/session.py
export const MODES = [
  {
    id: "conversation",
    short: "LIVE",
    label: "Conversational interview",
    description:
      "ARIA asks each question out loud and responds to what you say, with follow-ups — like a real interview. Needs a microphone and speakers.",
  },
  {
    id: "classic",
    short: "CLASSIC",
    label: "One question at a time",
    description:
      "Read each question on screen and answer by speaking or typing, with feedback after every answer.",
  },
];

export function getMode(id) {
  return MODES.find((mode) => mode.id === id) ?? MODES[1];
}
