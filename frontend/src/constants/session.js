// Mirrors MIN_ANSWERED_FOR_HISTORY in backend/app/services/interview_service.py.
// The backend is what actually enforces this (deciding completed vs.
// discarded when a session ends) — this copy is for messaging only, so the
// leave-confirmation dialog can explain the real threshold instead of a
// vague "some questions".
export const MIN_ANSWERED_FOR_HISTORY = 2;
