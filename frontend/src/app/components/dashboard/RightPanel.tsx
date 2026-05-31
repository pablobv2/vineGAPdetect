import type { DetectionItem, XAIResult } from "../../api/types";
import type { XAIScope } from "../../hooks/useDashboardState";

interface InferenceResults {
  detectionCount: number;
  meanConfidence: number;
  estimatedMissing: number;
  inferenceMs: number;
}

interface Props {
  viewMode: "inference" | "xai";
  results: InferenceResults | null;
  detections: DetectionItem[];
  confThreshold: number;
  xaiDetectionId: number | null;
  xaiScope: XAIScope;
  xaiConfThreshold: number;
  xaiResult: XAIResult | null;
  isHistoryRestored?: boolean;
  canExportGpkg: boolean;
  pdfGenerating?: boolean;
  onExportGPKG: () => void;
  onExportPDF: () => void;
}

export function RightPanel({
  viewMode, results, detections,
  confThreshold, xaiDetectionId, xaiScope, xaiConfThreshold, xaiResult, isHistoryRestored, canExportGpkg, pdfGenerating,
  onExportGPKG, onExportPDF,
}: Props) {
  const filtered = detections.filter(d => d.confidence >= confThreshold);
  const detectionLabel = xaiScope === "full"
    ? "parcela completa"
    : xaiDetectionId != null
    ? `#${String(xaiDetectionId).padStart(4, "0")}`
    : "mejor detección";
  const confidenceLabel = results
    ? `${(results.meanConfidence * 100).toFixed(1)}%`
    : "N/D";
  const xaiThresholdLabel = `${((xaiResult?.used_conf_threshold ?? xaiConfThreshold) * 100).toFixed(0)}%`;

  return (
    <aside style={{ width: 320, flexShrink: 0, borderLeft: "1px solid var(--vg-line)", background: "var(--vg-panel)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ overflowY: "auto", flex: 1, display: "flex", flexDirection: "column" }}>

        {/* ── Section label ── */}
        <div className="section-label">
          <span>Resultados</span>
        </div>

        {viewMode === "inference" && (
          <>
            {results ? (
              <>
                {/* Metric grid */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", borderTop: "1px solid var(--vg-line-soft)" }}>
                  <MetricBlock
                    label="Huecos detectados"
                    value={results.detectionCount.toString()}
                    accent
                  />
                  <MetricBlock
                    label="Confianza media"
                    value={`${(results.meanConfidence * 100).toFixed(1)}%`}
                    borderLeft
                  />
                  <MetricBlock
                    label="Marras estimadas"
                    value={results.estimatedMissing.toString()}
                    borderTop
                    accent
                  />
                  <MetricBlock
                    label="Tiempo inferencia"
                    value={results.inferenceMs >= 1000
                      ? `${(results.inferenceMs / 1000).toFixed(1)} s`
                      : `${results.inferenceMs} ms`}
                    borderLeft borderTop
                  />
                </div>

                {/* Confidence distribution */}
                <div style={{ padding: "12px 20px 16px", borderTop: "1px solid var(--vg-line-soft)" }}>
                  <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>
                    Distribución de confianza
                  </div>
                  <ConfidenceHistogram detections={filtered} />
                </div>

                {/* Export actions */}
                <div style={{ padding: "12px 20px 16px", borderTop: "1px solid var(--vg-line-soft)", display: "flex", flexDirection: "column", gap: 8, marginTop: "auto" }}>
                  <button
                    className="btn btn-quiet btn-full"
                    onClick={onExportGPKG}
                    disabled={!canExportGpkg}
                    title={canExportGpkg
                      ? "Descargar capa vectorial (.gpkg) para QGIS"
                      : "Solo disponible para GeoTIFF georreferenciado con detecciones"}
                  >
                    Exportar GeoPackage (QGIS)
                  </button>
                  <button
                    className="btn btn-quiet btn-full"
                    onClick={onExportPDF}
                    disabled={pdfGenerating}
                    title="Descargar informe PDF con resultados y detecciones"
                  >
                    {pdfGenerating ? "Generando PDF…" : "Exportar informe PDF"}
                  </button>
                </div>
              </>
            ) : (
              <div style={{ padding: "16px 20px", color: "var(--vg-ink-lo)", fontSize: 12.5, lineHeight: 1.55, borderTop: "1px solid var(--vg-line-soft)" }}>
                Ejecute la inferencia para ver los resultados aquí.
              </div>
            )}
          </>
        )}

        {viewMode === "xai" && (
          <>
            <div style={{ borderTop: "1px solid var(--vg-line-soft)" }}>
              <XaiFact label="Detección" value={detectionLabel} />
              <XaiFact label="Confianza media" value={confidenceLabel} />
              <XaiFact label="Umbral usado" value={xaiThresholdLabel} />
              <ActivationLegend />
              <TargetLayersBlock
                layers={xaiResult?.used_target_layers ?? [18]}
                method={xaiResult?.method ?? "Eigen-CAM"}
              />
              {isHistoryRestored && (
                <div style={{ padding: "12px 20px", borderTop: "1px solid var(--vg-line-soft)", color: "var(--vg-ink-lo)", fontSize: 12, lineHeight: 1.5 }}>
                  En historial el XAI se regenera desde el GeoTIFF guardado.
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

function MetricBlock({ label, value, accent, borderLeft, borderTop }: {
  label: string; value: string; accent?: boolean; borderLeft?: boolean; borderTop?: boolean;
}) {
  return (
    <div style={{
      padding: "16px 20px",
      borderLeft: borderLeft ? "1px solid var(--vg-line-soft)" : undefined,
      borderTop: borderTop ? "1px solid var(--vg-line-soft)" : undefined,
    }}>
      <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10, color: "var(--vg-ink-lo)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 500, letterSpacing: "-0.03em", color: accent ? "var(--vg-accent)" : "var(--vg-ink-hi)", lineHeight: 1 }}>
        {value}
      </div>
    </div>
  );
}

function ConfidenceHistogram({ detections }: { detections: DetectionItem[] }) {
  const buckets = [0, 0, 0, 0, 0]; // 50-60, 60-70, 70-80, 80-90, 90-100
  for (const d of detections) {
    const idx = Math.min(Math.floor((d.confidence - 0.5) / 0.1), 4);
    if (idx >= 0) buckets[idx]++;
  }
  const maxBucket = Math.max(...buckets, 1);
  const labels = ["50", "60", "70", "80", "90+"];

  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 44 }}>
      {buckets.map((count, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 3, height: "100%" }}>
          <div style={{ flex: 1, width: "100%", display: "flex", alignItems: "flex-end" }}>
            <div style={{
              width: "100%",
              height: `${(count / maxBucket) * 100}%`,
              minHeight: count > 0 ? 3 : 0,
              background: i >= 4 ? "#ff3333" : i >= 2 ? "#ff8800" : "#eab308",
            }} />
          </div>
          <div style={{ fontFamily: "var(--vg-mono)", fontSize: 9, color: "var(--vg-ink-lo)" }}>{labels[i]}</div>
        </div>
      ))}
    </div>
  );
}

function XaiFact({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 14, padding: "10px 20px", borderTop: "1px solid var(--vg-line-soft)" }}>
      <span style={{ color: "var(--vg-ink-md)", fontSize: 12 }}>{label}</span>
      <span style={{ color: "var(--vg-ink-hi)", fontSize: 12, fontFamily: "var(--vg-mono)", textAlign: "right" }}>{value}</span>
    </div>
  );
}

function ActivationLegend() {
  return (
    <div style={{ padding: "14px 20px 16px", borderTop: "1px solid var(--vg-line-soft)" }}>
      <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 10 }}>
        Activación
      </div>
      <div style={{ height: 10, background: "linear-gradient(90deg, #2436ff 0%, #1fa4ff 25%, #35d06f 50%, #f2d13d 74%, #d7191c 100%)", border: "1px solid var(--vg-line)", marginBottom: 8 }} />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--vg-ink-md)" }}>
        <span>Baja</span>
        <span>Media</span>
        <span>Alta</span>
      </div>
    </div>
  );
}

function TargetLayersBlock({ layers, method }: { layers: number[]; method: string }) {
  return (
    <div style={{ padding: "14px 20px 16px", borderTop: "1px solid var(--vg-line-soft)" }}>
      <div style={{ fontSize: 12, color: "var(--vg-ink-md)", marginBottom: 10 }}>
        Capas objetivo del modelo
      </div>
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        {layers.map((layer, i) => (
          <span
            key={layer}
            style={{
              padding: "4px 10px",
              fontFamily: "var(--vg-mono)",
              fontSize: 11,
              border: "1px solid var(--vg-accent)",
              color: "var(--vg-accent)",
              background: i === 0 ? "var(--vg-accent-soft)" : "transparent",
            }}
          >
            L{layer}
          </span>
        ))}
        <span style={{ marginLeft: "auto", fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)" }}>
          {method}
        </span>
      </div>
    </div>
  );
}
