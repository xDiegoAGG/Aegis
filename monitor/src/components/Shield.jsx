// The Aegis shield: a blue shield with a rising line that it keeps under control.
export default function Shield({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <linearGradient id="shield-fill" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#60a5fa" />
          <stop offset="1" stopColor="#1d4ed8" />
        </linearGradient>
      </defs>
      <path
        d="M32 4 L56 12 V30 C56 45 46 55 32 60 C18 55 8 45 8 30 V12 Z"
        fill="url(#shield-fill)"
        stroke="#bfdbfe"
        strokeWidth="2"
      />
      <path
        d="M20 38 L28 30 L34 35 L45 22"
        fill="none"
        stroke="#ffffff"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
