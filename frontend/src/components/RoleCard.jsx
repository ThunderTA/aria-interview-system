export default function RoleCard({ role, selected, onSelect }) {
  return (
    <button
      type="button"
      className={`role-card${selected ? " role-card--selected" : ""}`}
      onClick={() => onSelect(role.id)}
      aria-pressed={selected}
    >
      <span className="role-card__badge">{role.short}</span>
      <span className="role-card__label">{role.label}</span>
      <span className="role-card__description">{role.description}</span>
    </button>
  );
}
