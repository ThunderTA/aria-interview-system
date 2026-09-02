import { useId, useState } from "react";

export default function FormField({ label, type = "text", error, ...inputProps }) {
  const id = useId();
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === "password";
  const resolvedType = isPassword && revealed ? "text" : type;

  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      <div className="form-field__control">
        <input id={id} type={resolvedType} aria-invalid={!!error} {...inputProps} />
        {isPassword && (
          <button
            type="button"
            className="form-field__toggle"
            onClick={() => setRevealed((v) => !v)}
            aria-label={revealed ? "Hide password" : "Show password"}
          >
            {revealed ? "Hide" : "Show"}
          </button>
        )}
      </div>
      {error && <p className="form-field__error">{error}</p>}
    </div>
  );
}
