import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadResume } from "../api/resume";
import { createSession } from "../api/sessions";
import AppHeader from "../components/AppHeader";
import DifficultyPicker from "../components/DifficultyPicker";
import Notice from "../components/Notice";
import RoleCard from "../components/RoleCard";
import WizardProgress from "../components/WizardProgress";
import { difficultyLabel } from "../constants/difficulty";
import { ROLES, getRole } from "../constants/roles";
import "./Setup.css";

const STEP_LABELS = ["Resume", "Role", "Difficulty", "Review"];
const RESUME_STEP = 0;
const ROLE_STEP = 1;
const DIFFICULTY_STEP = 2;
const REVIEW_STEP = 3;

export default function Setup() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [step, setStep] = useState(RESUME_STEP);
  const [selectedRole, setSelectedRole] = useState(ROLES[0].id);
  const [difficulty, setDifficulty] = useState(null);
  const [fileName, setFileName] = useState(null);
  const [uploadState, setUploadState] = useState("idle");
  const [parsed, setParsed] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);
  const resumeReady = uploadState === "done" && parsed != null;

  const goTo = (target) => setStep(target);
  const back = () => setStep((s) => Math.max(RESUME_STEP, s - 1));
  const continueFromResume = () => resumeReady && setStep(ROLE_STEP);
  const continueFromRole = () => setStep(DIFFICULTY_STEP);
  const continueFromDifficulty = () => setStep(REVIEW_STEP);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setUploadState("uploading");
    setUploadError(null);
    try {
      const resume = await uploadResume(file);
      setParsed(resume);
      setUploadState("done");
      // Pre-select the role the resume points at; the candidate can still override.
      if (ROLES.some((role) => role.id === resume.inferred_role)) {
        setSelectedRole(resume.inferred_role);
      }
    } catch (err) {
      setUploadState("error");
      setUploadError(
        err.response?.data?.detail || "Could not read that file. Try a text-based PDF or .docx."
      );
    }
  };

  const handleStart = async () => {
    if (!resumeReady) return;
    setStarting(true);
    setStartError(null);
    try {
      const session = await createSession(selectedRole, difficulty);
      navigate("/interview", { state: { session } });
    } catch (err) {
      setStartError(
        err.response?.data?.detail ||
          "The interview engine isn't reachable. Check that `ollama serve` is running."
      );
      setStarting(false);
    }
  };

  const role = getRole(selectedRole);

  return (
    <div className="setup-shell">
      <AppHeader backTo="/dashboard" backLabel="Dashboard" />

      <WizardProgress steps={STEP_LABELS} current={step} />

      {step === RESUME_STEP && (
        <div className="wizard-step" key="resume">
          <p className="wizard-step__eyebrow">Step 1 of 4</p>
          <h1 className="wizard-step__title">Add your resume</h1>
          <p className="wizard-step__sub">
            ARIA tailors your questions to your actual experience, so this is required before you
            can start. PDF or Word — only the text is used, and it's discarded from memory once
            parsed.
          </p>

          <div
            className={`resume-drop${resumeReady ? " resume-drop--done" : " resume-drop--required"}`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={handleFileChange}
              hidden
            />
            <div className="resume-drop__body">
              <p className="resume-drop__name">{fileName ?? "No file selected"}</p>
              <p className="resume-drop__hint">PDF or Word document</p>
            </div>
            <button
              type="button"
              className="setup-secondary-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadState === "uploading"}
            >
              {uploadState === "uploading" ? "Uploading..." : "Choose file"}
            </button>
          </div>

          {uploadState === "error" && (
            <Notice title="Couldn't read that file.">{uploadError}</Notice>
          )}

          {uploadState === "done" && parsed && (
            <div className="resume-parsed">
              <div className="resume-parsed__summary">
                <span className="resume-parsed__chip resume-parsed__chip--accent">
                  {getRole(parsed.inferred_role).short}
                </span>
                <span className="resume-parsed__level">{parsed.inferred_level} level</span>
                <span className="resume-parsed__count">
                  {parsed.parsed_skills.length} skills detected
                </span>
              </div>
              <div className="resume-parsed__skills">
                {parsed.parsed_skills.map((skill) => (
                  <span key={skill.name} className="resume-parsed__chip">
                    {skill.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="wizard-nav">
            <span />
            <button
              type="button"
              className="setup-primary-button"
              onClick={continueFromResume}
              disabled={!resumeReady}
              title={resumeReady ? undefined : "Upload your resume to continue"}
            >
              Continue →
            </button>
          </div>
        </div>
      )}

      {step === ROLE_STEP && (
        <div className="wizard-step" key="role">
          <p className="wizard-step__eyebrow">Step 2 of 4</p>
          <h1 className="wizard-step__title">Choose a role</h1>
          <p className="wizard-step__sub">
            Pre-selected from your resume — pick a different one if you'd rather practise
            something else.
          </p>

          <div className="role-grid">
            {ROLES.map((r) => (
              <RoleCard
                key={r.id}
                role={r}
                selected={selectedRole === r.id}
                onSelect={setSelectedRole}
              />
            ))}
          </div>

          <div className="wizard-nav">
            <button type="button" className="wizard-back" onClick={back}>
              ← Back
            </button>
            <button type="button" className="setup-primary-button" onClick={continueFromRole}>
              Continue →
            </button>
          </div>
        </div>
      )}

      {step === DIFFICULTY_STEP && (
        <div className="wizard-step" key="difficulty">
          <p className="wizard-step__eyebrow">Step 3 of 4</p>
          <h1 className="wizard-step__title">Set a starting difficulty</h1>
          <p className="wizard-step__sub">
            {difficulty === null
              ? "ARIA starts near the level your resume suggests, then adjusts after every answer."
              : "This sets only the first question — ARIA still adjusts difficulty after that based on how you answer."}
          </p>

          <DifficultyPicker value={difficulty} onChange={setDifficulty} />

          <div className="wizard-nav">
            <button type="button" className="wizard-back" onClick={back}>
              ← Back
            </button>
            <button
              type="button"
              className="setup-primary-button"
              onClick={continueFromDifficulty}
            >
              Review →
            </button>
          </div>
        </div>
      )}

      {step === REVIEW_STEP && (
        <div className="wizard-step" key="review">
          <p className="wizard-step__eyebrow">Step 4 of 4</p>
          <h1 className="wizard-step__title">Review and start</h1>
          <p className="wizard-step__sub">
            Everything below is editable — jump back to a step, or start the interview as is.
          </p>

          <div className="review-list">
            <div className="review-row">
              <div>
                <p className="review-row__label">Resume</p>
                <p className="review-row__value">{fileName}</p>
                <p className="review-row__meta">
                  {parsed?.parsed_skills.length} skills detected · {parsed?.inferred_level} level
                </p>
              </div>
              <button type="button" className="review-row__edit" onClick={() => goTo(RESUME_STEP)}>
                Edit
              </button>
            </div>

            <div className="review-row">
              <div>
                <p className="review-row__label">Role</p>
                <p className="review-row__value">{role.label}</p>
              </div>
              <button type="button" className="review-row__edit" onClick={() => goTo(ROLE_STEP)}>
                Edit
              </button>
            </div>

            <div className="review-row">
              <div>
                <p className="review-row__label">Starting difficulty</p>
                <p className="review-row__value">
                  {difficulty === null ? "Auto (from resume)" : difficultyLabel(difficulty)}
                </p>
              </div>
              <button
                type="button"
                className="review-row__edit"
                onClick={() => goTo(DIFFICULTY_STEP)}
              >
                Edit
              </button>
            </div>
          </div>

          {startError && <Notice title="Couldn't start the interview.">{startError}</Notice>}

          <div className="wizard-nav">
            <button type="button" className="wizard-back" onClick={back}>
              ← Back
            </button>
            <button
              type="button"
              className="setup-primary-button"
              onClick={handleStart}
              disabled={starting}
            >
              {starting ? "Preparing your first question..." : "Start interview →"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
