import type { ParcelMetadata, ViewMode } from "../../hooks/useDashboardState";
import { PlayIcon } from "../Glyphs";

function nd(v: string | null | undefined) {
  const t = v?.trim();
  return t && t.length > 0 ? t : "N/D";
}

interface Props {
  viewMode: ViewMode | null;
  uploadedFile: File | null;
  displayFilename?: string;
  isHistoryRestored?: boolean;
  parcelMeta: ParcelMetadata | null;
  canRunAnalysis: boolean;
  confThreshold: number;
  vineWidth: number;
  inferenceRunning: boolean;
  inferenceDone: boolean;
  showInferenceLabels: boolean;
  historyId: number | null;
  isSaved: boolean;
  savingParcel: boolean;
  xaiOpacity: number;
  xaiShowDetections: boolean;
  xaiRunning: boolean;
  onSetConfThreshold: (v: number) => void;
  onSetVineWidth: (v: number) => void;
  onToggleLabels: () => void;
  onRunInference: () => void;
  onSaveParcel: () => void;
  onXaiOpacityChange: (v: number) => void;
  onToggleXaiDetections: () => void;
}

export function LeftRail({
  viewMode, uploadedFile, displayFilename, isHistoryRestored, parcelMeta, canRunAnalysis,
  confThreshold, vineWidth, inferenceRunning, inferenceDone, showInferenceLabels,
  historyId, isSaved, savingParcel,
  xaiOpacity, xaiShowDetections, xaiRunning,
  onSetConfThreshold, onSetVineWidth, onToggleLabels, onRunInference, onSaveParcel,
  onXaiOpacityChange, onToggleXaiDetections,
}: Props) {
  const areaText = parcelMeta?.areaHectares != null ? `${parcelMeta.areaHectares.toFixed(2)} ha` : "N/D";
  const centerText = parcelMeta?.centerLat != null && parcelMeta?.centerLon != null
    ? `${parcelMeta.centerLat.toFixed(6)} N · ${parcelMeta.centerLon.toFixed(6)} W`
    : "N/D";
  const resText = parcelMeta?.resolutionX != null && parcelMeta?.resolutionY != null
    ? `${parcelMeta.resolutionX.toFixed(3)} x ${parcelMeta.resolutionY.toFixed(3)} ${nd(parcelMeta.resolutionUnit)}`
    : "N/D";
  const dimsText = parcelMeta?.sourceWidth && parcelMeta?.sourceHeight
    ? `${parcelMeta.sourceWidth} x ${parcelMeta.sourceHeight} px`
    : "N/D";
  const filename = displayFilename ?? uploadedFile?.name;

  return (
    <aside style={{ width: 340, flexShrink: 0, borderRight: "1px solid var(--vg-line)", background: "var(--vg-panel)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ overflowY: "auto", flex: 1, display: "flex", flexDirection: "column" }}>
        {viewMode === "preview" && uploadedFile && (
          <>
            <div className="section-label" style={{ marginTop: 8 }}>
              <span>Vista previa</span>
            </div>
            <div style={{ padding: "12px 20px 16px", borderTop: "1px solid var(--vg-line-soft)" }}>
              <p style={{ fontSize: 12, color: "var(--vg-ink-md)", lineHeight: 1.5, marginBottom: 14 }}>
                El ortomosaico se muestra sin procesar. Cambia al modo detección para ejecutar inferencia.
              </p>
              {canRunAnalysis && (
                <button className="btn btn-accent btn-full" onClick={onRunInference} disabled={inferenceRunning}>
                  <PlayIcon /> {inferenceRunning ? "Ejecutando..." : "Ejecutar detección"}
                </button>
              )}
            </div>
          </>
        )}

        {viewMode === "inference" && (
          <>
            <div className="section-label" style={{ marginTop: 8 }}>
              <span>Parámetros de inferencia</span>
            </div>
            <SliderRow
              label="Umbral de confianza"
              value={confThreshold}
              displayVal={`${(confThreshold * 100).toFixed(0)}%`}
              min={0.05} max={0.95} step={0.05}
              onChange={onSetConfThreshold}
            />
            <SliderRow
              label="Ancho típico de cepa"
              value={vineWidth}
              displayVal={`${vineWidth.toFixed(1)} m`}
              min={0.5} max={3.0} step={0.1}
              onChange={onSetVineWidth}
              disabled={inferenceRunning || !canRunAnalysis}
            />
            <div className="vg-toggle-row">
              <span>Mostrar etiquetas</span>
              <div className={`vg-toggle ${showInferenceLabels ? "on" : ""}`} onClick={onToggleLabels}>
                <div className="vg-toggle-knob" />
              </div>
            </div>
            {canRunAnalysis && (
              <div style={{ padding: "12px 20px 16px", borderTop: "1px solid var(--vg-line-soft)" }}>
                <button className="btn btn-accent btn-full" onClick={onRunInference} disabled={inferenceRunning}>
                  <PlayIcon /> {inferenceRunning ? "Ejecutando..." : "Reejecutar inferencia"}
                </button>
              </div>
            )}
          </>
        )}

        {viewMode === "xai" && (
          <>
            <div className="section-label" style={{ marginTop: 8 }}>
              <span>Controles XAI</span>
            </div>
            {isHistoryRestored && (
              <div style={{ padding: "12px 20px", borderTop: "1px solid var(--vg-line-soft)", color: "var(--vg-ink-md)", fontSize: 12, lineHeight: 1.5 }}>
                El XAI de una parcela restaurada se calcula desde el GeoTIFF guardado de esa parcela.
              </div>
            )}
            <div className="vg-toggle-row">
              <span>Mostrar detecciones</span>
              <div className={`vg-toggle ${xaiShowDetections ? "on" : ""}`} onClick={onToggleXaiDetections}>
                <div className="vg-toggle-knob" />
              </div>
            </div>
            <SliderRow
              label="Opacidad del mapa"
              value={xaiOpacity}
              displayVal={`${(xaiOpacity * 100).toFixed(0)}%`}
              min={0.15} max={0.95} step={0.05}
              onChange={onXaiOpacityChange}
              disabled={xaiRunning}
            />
          </>
        )}

        {inferenceDone && !isHistoryRestored && historyId && (
          <div style={{ padding: "12px 20px 16px", borderTop: "1px solid var(--vg-line-soft)" }}>
            {isSaved ? (
              <div style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "9px 12px",
                background: "color-mix(in srgb, #22c55e 12%, transparent)",
                border: "1px solid color-mix(in srgb, #22c55e 50%, transparent)",
                color: "#22c55e", fontSize: 13,
              }}>
                <span style={{ fontWeight: 600 }}>✓</span> Parcela guardada en Mis parcelas
              </div>
            ) : (
              <button
                className="btn btn-accent btn-full"
                onClick={onSaveParcel}
                disabled={savingParcel}
                title="Guardar esta parcela y sus detecciones en Mis parcelas"
              >
                {savingParcel ? "Guardando..." : "Guardar parcela"}
              </button>
            )}
          </div>
        )}

        <div className="section-label" style={{ marginTop: 8 }}>
          <span>Ficha técnica</span>
        </div>

        {uploadedFile ? (
          <>
            <MetaRow k="Parcela" v={(filename ?? uploadedFile.name).replace(/\.[^.]+$/, "")} />
            <MetaRow k="Archivo" v={filename ?? uploadedFile.name} mono />
            {isHistoryRestored && <MetaRow k="Origen" v="Historial restaurado" mono />}
            <MetaRow k="Formato" v={nd(parcelMeta?.fileType)} mono />
            <MetaRow k="Dimensiones" v={dimsText} mono />
            <MetaRow k="Superficie" v={areaText} mono />
            <MetaRow k="GSD" v={resText} mono />
            <MetaRow k="CRS" v={nd(parcelMeta?.crs)} mono />
            <MetaRow k="Centro" v={centerText} mono />
          </>
        ) : (
          <div style={{ padding: "16px 20px", color: "var(--vg-ink-lo)", fontSize: 12.5, lineHeight: 1.55, borderTop: "1px solid var(--vg-line-soft)" }}>
            Ningún ortomosaico cargado. Los metadatos georreferenciados aparecerán aquí tras la carga.
          </div>
        )}
      </div>
    </aside>
  );
}

function MetaRow({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="meta-row">
      <span className="meta-row-key">{k}</span>
      <span className={`meta-row-val${mono ? " mono" : ""}`}>{v}</span>
    </div>
  );
}

function SliderRow({ label, value, displayVal, min, max, step, onChange, disabled }: {
  label: string; value: number; displayVal: string;
  min: number; max: number; step: number;
  onChange: (v: number) => void; disabled?: boolean;
}) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className="vg-slider-wrap">
      <div className="vg-slider-head">
        <span>{label}</span>
        <span className="vg-slider-val">{displayVal}</span>
      </div>
      <div style={{ position: "relative" }}>
        <div className="vg-slider-track">
          <div className="vg-slider-fill" style={{ width: `${pct}%` }} />
          <div className="vg-slider-thumb" style={{ left: `${pct}%` }} />
        </div>
        <input
          type="range" className="vg-range"
          min={min} max={max} step={step} value={value}
          disabled={disabled}
          onChange={e => onChange(Number(e.target.value))}
          style={{ position: "absolute", inset: 0, opacity: 0, cursor: disabled ? "not-allowed" : "pointer" }}
        />
      </div>
      <div className="vg-slider-labels"><span>{min}</span><span>{max}</span></div>
    </div>
  );
}
