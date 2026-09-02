import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadResume } from "../api/resume";
import AppHeader from "../components/AppHeader";
import Notice from "../components/Notice";
import RoleCard from "../components/RoleCard";
import { ROLES, getRole } from "../constants/roles";
import "./Setup.css";

export default function Setup() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [selectedRole, setSelectedRole] = useState(ROLES[0].id);
  const [fileName, setFileName] = useState(null);
  const [uploadState, setUploadState] = useState("idle");
  const [parsed, setParsed] = useState(null);
  const [uploadError, setUploadError] = useState(null);

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

  return (
    <div className="setup-shell">
      <AppHeader backTo="/dashboard" backLabel="Dashboard" />

      <div className="setup-intro">
        <h1>Set up your interview</h1>
        <p>Add your resume for tailored questions, then pick the role you want to practise.</p>
      </div>

      <section className="setup-section">
        <div className="setup-section__head">
          <h2>1 · Resume</h2>
          <span className="setup-optional">Optional</span>
        </div>

        <div className="resume-drop">
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

        {uploadState === "error" && <Notice title="Couldn't read that file.">{uploadError}</Notice>}

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
      </section>

      <section className="setup-section">
        <div className="setup-section__head">
          <h2>2 · Role</h2>
        </div>
        <div className="role-grid">
          {ROLES.map((role) => (
            <RoleCard
              key={role.id}
              role={role}
              selected={selectedRole === role.id}
              onSelect={setSelectedRole}
            />
          ))}
        </div>
      </section>

      <div className="setup-actions">
        <Notice variant="preview" title="Preview mode.">
          Live interviews need the speech and scoring engines, which aren't built yet. Continuing
          shows the interview screens as a UI preview.
        </Notice>
        <button
          type="button"
          className="setup-primary-button"
          onClick={() => navigate("/interview", { state: { role: selectedRole } })}
        >
          Continue to preview →
        </button>
      </div>
    </div>
  );
}
