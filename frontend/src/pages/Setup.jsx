import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadResume } from "../api/resume";
import AppHeader from "../components/AppHeader";
import Notice from "../components/Notice";
import RoleCard from "../components/RoleCard";
import { ROLES } from "../constants/roles";
import "./Setup.css";

export default function Setup() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [selectedRole, setSelectedRole] = useState(ROLES[0].id);
  const [fileName, setFileName] = useState(null);
  const [uploadState, setUploadState] = useState("idle");

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setUploadState("uploading");
    try {
      await uploadResume(file);
      setUploadState("done");
    } catch {
      // POST /resume/upload is still a 501 stub — expected, not an error worth alarming about.
      setUploadState("unavailable");
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

        {uploadState === "unavailable" && (
          <Notice title="Not wired up yet.">
            Resume parsing arrives with the LLM milestone, so this file wasn't processed. Pick
            your role below to continue.
          </Notice>
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
