import type { ViewMode } from "../../hooks/useDashboardState";

interface Props {
  active: ViewMode | null;
  canRunAnalysis: boolean;
  hasImage: boolean;
  onChange: (mode: ViewMode) => void;
}

const TABS: { id: ViewMode; mono: string; label: string }[] = [
  { id: "preview",   mono: "VIEW",  label: "Vista previa" },
  { id: "inference", mono: "INFERENCE", label: "Detección de marras" },
  { id: "xai",       mono: "XAI",   label: "Explicabilidad" },
];

export function ModeTabs({ active, canRunAnalysis, hasImage, onChange }: Props) {
  return (
    <div style={{ display: "flex", borderBottom: "1px solid var(--vg-line)", background: "var(--vg-panel)", flexShrink: 0 }}>
      {TABS.map(t => {
        const isActive = active === t.id;
        const disabled = !hasImage || ((t.id === "inference" || t.id === "xai") && !canRunAnalysis);
        return (
          <button
            key={t.id}
            className={`mode-tab${isActive ? " active" : ""}${disabled ? " disabled" : ""}`}
            onClick={() => !disabled && onChange(t.id)}
            disabled={disabled}
          >
            <span className="mode-tab-mono">{t.mono}</span>
            <span className="mode-tab-label">{t.label}</span>
          </button>
        );
      })}
      <div style={{ flex: 1 }} />
    </div>
  );
}
