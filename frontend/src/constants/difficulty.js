// ids must line up with the 1-5 range the backend accepts as
// SessionCreate.starting_difficulty and with rl_engine's difficulty scale.
export const DIFFICULTY_LEVELS = [
  { id: 1, label: "Warm-up" },
  { id: 2, label: "Easy" },
  { id: 3, label: "Moderate" },
  { id: 4, label: "Challenging" },
  { id: 5, label: "Hard" },
];

export function difficultyLabel(id) {
  return DIFFICULTY_LEVELS.find((d) => d.id === id)?.label ?? "Moderate";
}
