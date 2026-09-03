// Small line icons for the landing page's feature/technology cards. Kept as
// plain stroke-based SVGs (no icon library) to match Logo.jsx's minimal
// geometric style, and always rendered inside an IconChip so they sit on a
// tinted circle rather than needing to pass contrast against the page
// themselves.

const common = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function IconChip({ tint = "accent", children }) {
  return <span className={`icon-chip icon-chip--${tint}`}>{children}</span>;
}

export const ResumeIcon = () => (
  <svg {...common} width="20" height="20">
    <path d="M7 3h7l4 4v14H7z" />
    <path d="M14 3v4h4" />
    <path d="M9.5 13h5M9.5 16.5h5M9.5 9.5h2" />
  </svg>
);

export const AdaptiveIcon = () => (
  <svg {...common} width="20" height="20">
    <path d="M4 19V9M10 19V5M16 19v-7M20 19V3" />
  </svg>
);

export const ScoreIcon = () => (
  <svg {...common} width="20" height="20">
    <rect x="4" y="4" width="16" height="16" rx="3" />
    <path d="M8 12l2.5 2.5L16 9" />
  </svg>
);

export const EyeIcon = () => (
  <svg {...common} width="20" height="20">
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
    <circle cx="12" cy="12" r="2.6" />
  </svg>
);

export const ShieldIcon = () => (
  <svg {...common} width="20" height="20">
    <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
    <path d="M9.2 12l2 2 3.6-4" />
  </svg>
);

export const TrendIcon = () => (
  <svg {...common} width="20" height="20">
    <path d="M3.5 16.5l6-6.5 4 4 7-8" />
    <path d="M15 6h5.5v5.5" />
  </svg>
);

export const MicIcon = () => (
  <svg {...common} width="20" height="20">
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0" />
    <path d="M12 17.5V21M8.5 21h7" />
  </svg>
);

export const BrainIcon = () => (
  <svg {...common} width="20" height="20">
    <path d="M9 4.5a2.6 2.6 0 0 0-2.6 2.6 2.7 2.7 0 0 0-1.9 4.6A2.9 2.9 0 0 0 6 16.9a2.7 2.7 0 0 0 3 2.6 2.6 2.6 0 0 0 2.6-2.5V7a2.6 2.6 0 0 0-2.6-2.5Z" />
    <path d="M15 4.5A2.6 2.6 0 0 1 17.6 7a2.7 2.7 0 0 1 1.9 4.6A2.9 2.9 0 0 1 18 16.9a2.7 2.7 0 0 1-3 2.6A2.6 2.6 0 0 1 12.4 17" />
  </svg>
);

export const CameraIcon = () => (
  <svg {...common} width="20" height="20">
    <path d="M4 8h3l1.5-2h7L17 8h3v11H4z" />
    <circle cx="12" cy="13.5" r="3.2" />
  </svg>
);

export const PolicyIcon = () => (
  <svg {...common} width="20" height="20">
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </svg>
);
