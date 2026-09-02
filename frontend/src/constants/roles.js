// ids must match SessionRole in backend/app/models/session.py
export const ROLES = [
  {
    id: "SDE",
    label: "Software Development Engineer",
    short: "SDE",
    description: "Data structures, system design, and language fundamentals for your stack.",
  },
  {
    id: "HR",
    label: "HR / Behavioral",
    short: "HR",
    description: "Motivation, teamwork, conflict, and the story behind your resume.",
  },
];

export function getRole(id) {
  return ROLES.find((role) => role.id === id) ?? ROLES[0];
}
