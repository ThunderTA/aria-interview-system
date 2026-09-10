import { useEffect } from "react";
import "./ConfirmDialog.css";

/**
 * A styled confirm/cancel modal — used in place of window.confirm() so it
 * matches the rest of the app instead of looking like a generic browser
 * prompt. Cancel is the button that gets focus: leaving is the consequential
 * action here, so the safe choice should be the default one Enter/Tab lands
 * on, not the one that discards something.
 *
 * `busy` locks both buttons and the overlay/Escape dismissal while onConfirm
 * is still running. Without it, a click on Cancel mid-confirm closes the
 * dialog but leaves the in-flight onConfirm free to finish and act anyway —
 * its callback was already captured when the click happened, so closing the
 * dialog doesn't cancel it, it just hides the fact that it's still going to
 * fire.
 */
export default function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "neutral",
  busy = false,
  onConfirm,
  onCancel,
}) {
  const cancel = () => {
    if (!busy) onCancel();
  };

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") cancel();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div className="confirm-overlay" onClick={cancel}>
      <div
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-dialog-title">{title}</h2>
        <div className="confirm-dialog__body">{children}</div>
        <div className="confirm-dialog__actions">
          <button
            type="button"
            className="confirm-dialog__cancel"
            onClick={cancel}
            disabled={busy}
            autoFocus
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`confirm-dialog__confirm confirm-dialog__confirm--${tone}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
