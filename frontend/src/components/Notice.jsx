export default function Notice({ variant = "info", title, children }) {
  return (
    <div className={`notice notice--${variant}`}>
      {title && <strong className="notice__title">{title}</strong>}
      <span>{children}</span>
    </div>
  );
}
