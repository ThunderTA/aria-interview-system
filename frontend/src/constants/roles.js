// ids must match SessionRole in backend/app/models/session.py
export const ROLES = [
  {
    id: "SDE",
    label: "Software Development Engineer",
    short: "SDE",
    description: "Data structures, system design, and language fundamentals for your stack.",
  },
  {
    id: "DS",
    label: "Data Scientist",
    short: "DS",
    description: "Statistics, experiment design, SQL, and machine learning fundamentals.",
  },
  {
    id: "MLE",
    label: "ML Engineer",
    short: "MLE",
    description: "Model deployment, MLOps, feature pipelines, and production trade-offs.",
  },
  {
    id: "QA",
    label: "QA / Test Engineer",
    short: "QA",
    description: "Test strategy, automation, bug triage, and release confidence.",
  },
  {
    id: "PM",
    label: "Product Manager",
    short: "PM",
    description: "Prioritization, product sense, metrics, and shipping a feature end to end.",
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
