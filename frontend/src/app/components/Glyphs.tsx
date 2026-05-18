// SVG icon primitives — hairline stroke, no fill, 1.25 stroke-width
const S = { fill: "none", stroke: "currentColor", strokeWidth: 1.25, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export function VGMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 22 22">
      <g {...S} stroke="var(--vg-accent)">
        <line x1="3" y1="5" x2="19" y2="5" />
        <line x1="3" y1="11" x2="19" y2="11" />
        <line x1="3" y1="17" x2="19" y2="17" />
        <circle cx="5.5" cy="5" r="0.9" fill="currentColor" />
        <circle cx="11" cy="5" r="0.9" fill="currentColor" />
        <circle cx="16.5" cy="5" r="0.9" fill="currentColor" />
        <circle cx="5.5" cy="11" r="0.9" fill="currentColor" />
        <circle cx="16.5" cy="11" r="0.9" fill="currentColor" />
        <circle cx="5.5" cy="17" r="0.9" fill="currentColor" />
        <circle cx="11" cy="17" r="0.9" fill="currentColor" />
        <circle cx="16.5" cy="17" r="0.9" fill="currentColor" />
        <rect x="9.2" y="9.2" width="3.6" height="3.6" stroke="var(--vg-accent)" strokeDasharray="2 1.5" fill="none" />
      </g>
    </svg>
  );
}

export function MoonIcon() { return <svg width="16" height="16" viewBox="0 0 16 16"><path {...S} d="M12.5 9.5A4.5 4.5 0 0 1 6.5 3.5 5 5 0 1 0 12.5 9.5z" /></svg>; }
export function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16">
      <circle {...S} cx="8" cy="8" r="2.5" />
      <g {...S}>
        <line x1="8" y1="1.5" x2="8" y2="3" /><line x1="8" y1="13" x2="8" y2="14.5" />
        <line x1="1.5" y1="8" x2="3" y2="8" /><line x1="13" y1="8" x2="14.5" y2="8" />
        <line x1="3.5" y1="3.5" x2="4.5" y2="4.5" /><line x1="11.5" y1="11.5" x2="12.5" y2="12.5" />
        <line x1="3.5" y1="12.5" x2="4.5" y2="11.5" /><line x1="11.5" y1="4.5" x2="12.5" y2="3.5" />
      </g>
    </svg>
  );
}
export function LogoutIcon() { return <svg width="16" height="16" viewBox="0 0 16 16"><path {...S} d="M9.5 4V2.5h-7v11h7V12M6 8h8M11.5 5.5L14 8l-2.5 2.5" /></svg>; }
export function PlusIcon() { return <svg width="12" height="12" viewBox="0 0 12 12"><path {...S} d="M6 1.5v9M1.5 6h9" /></svg>; }
export function ChevronRightIcon() { return <svg width="10" height="10" viewBox="0 0 12 14"><path {...S} d="M5 3l4 4-4 4" /></svg>; }
export function DownloadIcon() { return <svg width="12" height="12" viewBox="0 0 14 14"><path {...S} d="M7 1.5v8M4 6.5l3 3 3-3M2 12h10" /></svg>; }
export function UploadIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22">
      <g {...S}>
        <path d="M11 14V3" /><path d="M6 8l5-5 5 5" /><path d="M3 17h16" />
      </g>
    </svg>
  );
}
export function ZoomInIcon() { return <svg width="14" height="14" viewBox="0 0 14 14"><g {...S}><circle cx="6" cy="6" r="3.5" /><line x1="8.6" y1="8.6" x2="12" y2="12" /><line x1="6" y1="4.5" x2="6" y2="7.5" /><line x1="4.5" y1="6" x2="7.5" y2="6" /></g></svg>; }
export function ZoomOutIcon() { return <svg width="14" height="14" viewBox="0 0 14 14"><g {...S}><circle cx="6" cy="6" r="3.5" /><line x1="8.6" y1="8.6" x2="12" y2="12" /><line x1="4.5" y1="6" x2="7.5" y2="6" /></g></svg>; }
export function ResetViewIcon() { return <svg width="14" height="14" viewBox="0 0 14 14"><path {...S} d="M2 7a5 5 0 1 1 1.5 3.5M2 11V8h3" /></svg>; }
export function PlayIcon() { return <svg width="11" height="11" viewBox="0 0 11 11"><path d="M2 1.5l7 4-7 4z" fill="currentColor" /></svg>; }
export function CloseIcon() { return <svg width="12" height="12" viewBox="0 0 12 12"><path {...S} d="M1.5 1.5l9 9M10.5 1.5l-9 9" /></svg>; }
export function NorthArrowIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14">
      <g transform="rotate(15 7 7)">
        <path d="M7 1.5L9 7H7V12.5H5V7H7z M7 1.5L5 7" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      </g>
    </svg>
  );
}
export function CrosshairIcon() { return <svg width="14" height="14" viewBox="0 0 14 14"><g {...S}><circle cx="7" cy="7" r="4" /><line x1="7" y1="0.5" x2="7" y2="3" /><line x1="7" y1="11" x2="7" y2="13.5" /><line x1="0.5" y1="7" x2="3" y2="7" /><line x1="11" y1="7" x2="13.5" y2="7" /></g></svg>; }
