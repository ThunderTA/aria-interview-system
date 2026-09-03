export default function Logo({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect x="9" y="14" width="2.6" height="4" rx="1.3" fill="var(--signal-text)" />
      <rect x="14.7" y="9" width="2.6" height="14" rx="1.3" fill="var(--accent-text)" />
      <rect x="20.4" y="12" width="2.6" height="8" rx="1.3" fill="var(--signal-text)" />
    </svg>
  );
}
