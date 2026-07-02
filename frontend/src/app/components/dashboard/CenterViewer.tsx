import { useCallback, useRef, useState } from "react";
import type { ViewMode, XAIScope } from "../../hooks/useDashboardState";
import type { DetectionItem, XAIResult } from "../../api/types";
import { InferenceCanvas, type InferenceCanvasHandle } from "../InferenceCanvas";
import { CloseIcon, CrosshairIcon, PlayIcon, ResetViewIcon, UploadIcon, ZoomInIcon, ZoomOutIcon } from "../Glyphs";

interface Props {
  viewMode: ViewMode | null;
  imageUrl: string | null;
  isHistoryRestored?: boolean;
  previewLoading: boolean;
  detections: DetectionItem[];
  sourceWidth?: number;
  sourceHeight?: number;
  showInferenceLabels: boolean;
  inferenceRunning: boolean;
  inferenceDone: boolean;
  inferenceProgress: number;
  xaiRunning: boolean;
  xaiDone: boolean;
  xaiScope: XAIScope;
  xaiDataUrl: string | null;
  xaiOverlayDataUrl: string | null;
  xaiResult: XAIResult | null;
  xaiOpacity: number;
  xaiShowDetections: boolean;
  zoom: number;
  visibleFeatureCount: number;
  canvasRef: React.RefObject<InferenceCanvasHandle | null>;
  onFileProcess: (file: File) => void;
  onClose: () => void;
  onZoomChange: (scale: number) => void;
  onFeatureCountChange: (count: number) => void;
}

export function CenterViewer({
  viewMode, imageUrl, isHistoryRestored, previewLoading,
  detections, sourceWidth, sourceHeight, showInferenceLabels,
  inferenceRunning, inferenceDone, inferenceProgress,
  xaiRunning, xaiDone, xaiScope, xaiDataUrl, xaiOverlayDataUrl, xaiResult, xaiOpacity, xaiShowDetections,
  zoom, visibleFeatureCount,
  canvasRef, onFileProcess, onClose, onZoomChange, onFeatureCountChange,
}: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFileProcess(file);
  }, [onFileProcess]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileProcess(file);
  };

  // Empty / loading state
  if (!imageUrl) {
    return (
      <main style={{ flex: 1, display: "flex", flexDirection: "column", padding: "28px 36px 24px", gap: 22, overflow: "auto", background: "var(--vg-bg)", minWidth: 0 }}>

        {/* Hero header */}
        <div style={{ maxWidth: 760 }}>
          <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-accent)", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 8 }}>
            vineGAPdetect · análisis vitícola
          </div>
          <h1 style={{ fontSize: 30, fontWeight: 500, letterSpacing: "-0.025em", lineHeight: 1.1, margin: "0 0 10px" }}>
            {previewLoading ? "Generando vista previa…" : "Detección y análisis de marras"}
          </h1>
          <p style={{ fontSize: 13.5, lineHeight: 1.5, color: "var(--vg-ink-md)", maxWidth: 640, margin: 0 }}>
            Cuantifica los huecos (cepas faltantes o muertas) en tus parcelas a partir de un
            ortomosaico aéreo. La inferencia combina <span style={{ color: "var(--vg-ink-hi)" }}>YOLOv11-OBB</span> con
            slicing <span style={{ color: "var(--vg-ink-hi)" }}>SAHI</span>, y permite inspeccionar cada decisión del modelo
            mediante <span style={{ color: "var(--vg-ink-hi)" }}>Eigen-CAM</span>.
          </p>
        </div>

        {previewLoading ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ textAlign: "center" }}>
              <div className="spinner" style={{ width: 36, height: 36, margin: "0 auto 16px" }} />
              <p style={{ color: "var(--vg-ink-lo)", fontSize: 13 }}>Procesando imagen…</p>
            </div>
          </div>
        ) : (
          <>
            {/* Pipeline overview */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              border: "1px solid var(--vg-line)",
              background: "var(--vg-panel)",
            }}>
              <PipelineStep
                num="01"
                title="Cargar ortomosaico"
                desc="GeoTIFF georreferenciado de la parcela. Se conserva el CRS original."
                icon={<UploadIcon />}
              />
              <PipelineStep
                num="02"
                title="Detección automática"
                desc="YOLOv11-OBB + SAHI localiza cada hueco con bounding box orientado."
                icon={<CrosshairIcon />}
                borderLeft
              />
              <PipelineStep
                num="03"
                title="Análisis y trazabilidad"
                desc="Métricas por parcela, exportación CSV/PDF y mapas Eigen-CAM por caja."
                icon={<PlayIcon />}
                borderLeft
              />
            </div>

            {/* Drop zone */}
            <div
              className={`drop-zone${isDragging ? " dragging" : ""}`}
              style={{ padding: "32px 36px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 40, minHeight: 170 }}
              onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input ref={fileInputRef} type="file" accept=".tif,.tiff,image/*" style={{ display: "none" }} onChange={handleFileChange} />
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--vg-accent)", marginBottom: 8 }}>
                  <UploadIcon />
                  <span style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, letterSpacing: "0.12em", textTransform: "uppercase" }}>Empieza aquí</span>
                </div>
                <h3 style={{ fontSize: 17, fontWeight: 500, letterSpacing: "-0.02em", margin: "0 0 5px" }}>
                  Carga de ortomosaico para an?lisis
                </h3>
                <p style={{ color: "var(--vg-ink-md)", fontSize: 12, lineHeight: 1.5, maxWidth: 460, margin: 0 }}>
                  GeoTIFF / TIFF / PNG / JPG. Los mosaicos pueden pesar varios GB — la vista previa
                  se genera en segundo plano.
                </p>
                <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                  <button className="btn btn-primary" onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                    Seleccionar archivo
                  </button>
                </div>
              </div>
              <div style={{
                fontFamily: "var(--vg-mono)", fontSize: 10, letterSpacing: "0.06em",
                color: "var(--vg-ink-lo)", borderLeft: "1px solid var(--vg-line)", paddingLeft: 22,
                display: "grid", gap: 8, minWidth: 200, flexShrink: 0,
              }}>
                <div><div style={{ color: "var(--vg-ink-xl)", marginBottom: 2 }}>FORMATOS</div>.tif · .tiff · .png · .jpg</div>
                <div><div style={{ color: "var(--vg-ink-xl)", marginBottom: 2 }}>TAMAÑO MÁX.</div>8 GB por archivo</div>
                <div><div style={{ color: "var(--vg-ink-xl)", marginBottom: 2 }}>BANDAS</div>RGB · RGBN · multiespectral</div>
                <div><div style={{ color: "var(--vg-ink-xl)", marginBottom: 2 }}>CRS</div>se conserva el original</div>
              </div>
            </div>
          </>
        )}
      </main>
    );
  }

  // XAI result view
  if (viewMode === "xai") {
    return (
      <main style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden", background: "var(--vg-bg)" }}>
        <ViewerToolbar
          zoom={zoom} hasClose onClose={onClose}
          onZoomIn={() => canvasRef.current?.zoomIn()}
          onZoomOut={() => canvasRef.current?.zoomOut()}
          onReset={() => canvasRef.current?.resetView()}
        />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 24, gap: 16, overflow: "hidden", minHeight: 0 }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", flexShrink: 0 }}>
            <div>
              <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 4 }}>
                Eigen-CAM sobre parcela completa
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 500, letterSpacing: "-0.02em", margin: 0 }}>Mapa de activaciones del modelo</h2>
            </div>
            {xaiResult && (
              <div style={{ display: "flex", gap: 16, fontFamily: "var(--vg-mono)", fontSize: 11, color: "var(--vg-ink-lo)" }}>
                <span>umbral {(xaiResult.used_conf_threshold ?? 0.55).toFixed(2)}</span>
                <span>capa L{(xaiResult.used_target_layers ?? [18]).join(",L")}</span>
              </div>
            )}
          </div>

          {/* Full parcel heatmap or tile strip */}
          <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", justifyContent: "center" }}>
            {xaiRunning && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
                <div className="spinner" style={{ width: 36, height: 36 }} />
                <p style={{ fontFamily: "var(--vg-mono)", fontSize: 13, color: "var(--vg-ink-lo)" }}>Generando Eigen-CAM…</p>
              </div>
            )}
            {xaiDone && imageUrl && xaiOverlayDataUrl && (
              <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
                <InferenceCanvas
                  ref={canvasRef}
                  imageUrl={imageUrl}
                  overlayUrl={xaiOverlayDataUrl}
                  detections={xaiShowDetections ? detections : []}
                  sourceWidth={sourceWidth}
                  sourceHeight={sourceHeight}
                  showLabels={xaiShowDetections && showInferenceLabels}
                  overlayOpacity={xaiOpacity}
                  onScaleChange={onZoomChange}
                  onFeatureCountChange={onFeatureCountChange}
                />
                <div style={{
                  position: "absolute", left: 16, bottom: 14, pointerEvents: "none",
                  padding: "6px 10px", background: "rgba(15,16,12,0.78)", color: "#fff",
                  fontFamily: "var(--vg-mono)", fontSize: 11,
                }}>
                  Eigen-CAM · parcela completa
                </div>
              </div>
            )}
            {!xaiRunning && !xaiDone && isHistoryRestored && (
              <div style={{ maxWidth: 620, margin: "0 auto", textAlign: "center", color: "var(--vg-ink-md)", fontSize: 13, lineHeight: 1.55 }}>
                Esta parcela restaurada necesita regenerar XAI desde el GeoTIFF guardado. El modo XAI inicia el c?lculo.
              </div>
            )}
            {!xaiRunning && !xaiDone && !isHistoryRestored && (
              <p style={{ color: "var(--vg-ink-lo)", fontSize: 13, textAlign: "center" }}>
                Genera el mapa de activación de la parcela completa desde el panel izquierdo.
              </p>
            )}
          </div>
        </div>
      </main>
    );
  }

  // Image viewer (preview / inference)
  return (
    <main style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden", background: "var(--vg-bg)" }}>
      <ViewerToolbar
        zoom={zoom}
        hasClose
        onClose={onClose}
        onZoomIn={() => canvasRef.current?.zoomIn()}
        onZoomOut={() => canvasRef.current?.zoomOut()}
        onReset={() => canvasRef.current?.resetView()}
        modeLabel={viewMode === "inference" ? "Detección · YOLO" : "Vista previa"}
      />

      {/* Progress bar for inference */}
      {inferenceRunning && (
        <div className="progress-bar" style={{ flexShrink: 0 }}>
          <div className="progress-fill" style={{ width: `${inferenceProgress}%` }} />
        </div>
      )}

      {/* Canvas */}
      <div style={{ flex: 1, position: "relative", minHeight: 0 }}>
        <InferenceCanvas
          ref={canvasRef}
          imageUrl={imageUrl}
          detections={viewMode === "inference" ? detections : []}
          sourceWidth={sourceWidth}
          sourceHeight={sourceHeight}
          showLabels={showInferenceLabels}
          onScaleChange={onZoomChange}
          onFeatureCountChange={onFeatureCountChange}
        />

        {/* Crosshair */}
        <div style={{ position: "absolute", top: "40%", left: "52%", color: "rgba(255,255,255,0.5)", mixBlendMode: "difference", pointerEvents: "none" }}>
          <CrosshairIcon />
        </div>

        {/* Scale bar */}
        <div style={{ position: "absolute", bottom: 14, left: 16, pointerEvents: "none" }}>
          <div className="scalebar">
            <div className="scalebar-bar">
              <div style={{ width: 40, background: "rgba(255,255,255,0.95)" }} />
              <div style={{ width: 40, background: "transparent" }} />
              <div style={{ width: 40, background: "rgba(255,255,255,0.95)" }} />
            </div>
            <div className="scalebar-labels"><span>0</span><span>10</span><span>20 m</span></div>
          </div>
        </div>

        {/* Zoom controls */}
        <div style={{ position: "absolute", bottom: 14, right: 16, display: "flex", alignItems: "stretch", background: "rgba(15,16,12,0.78)", color: "#fff" }}>
          <button className="btn-icon-viewer" onClick={() => canvasRef.current?.zoomOut()}><ZoomOutIcon /></button>
          <div style={{ padding: "0 12px", display: "flex", alignItems: "center", fontFamily: "var(--vg-mono)", fontSize: 11, borderLeft: "1px solid rgba(255,255,255,0.18)", borderRight: "1px solid rgba(255,255,255,0.18)" }}>
            {Math.round(zoom * 100)}%
          </div>
          <button className="btn-icon-viewer" onClick={() => canvasRef.current?.zoomIn()}><ZoomInIcon /></button>
          <button className="btn-icon-viewer" onClick={() => canvasRef.current?.resetView()}><ResetViewIcon /></button>
        </div>

        {/* Running overlay */}
        {inferenceRunning && (
          <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, display: "flex", alignItems: "center", gap: 12, borderTop: "1px solid rgba(255,255,255,0.1)", background: "rgba(15,16,12,0.88)", padding: "10px 16px" }}>
            <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--vg-mono)", fontSize: 11, color: "rgba(255,255,255,0.7)", marginBottom: 4 }}>
                <span>Ejecutando inferencia…</span>
                <span style={{ color: "var(--vg-accent)" }}>{inferenceProgress}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${inferenceProgress}%` }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Confidence legend */}
      {viewMode === "inference" && inferenceDone && (
        <div style={{
          flexShrink: 0, display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap",
          padding: "7px 16px", borderTop: "1px solid var(--vg-line)",
          background: "var(--vg-panel)", fontFamily: "var(--vg-mono)", fontSize: 11,
          color: "var(--vg-ink-md)",
        }}>
          {([
            { color: "#ff3333", label: "Alta confianza (≥ 60 %)" },
            { color: "#ff8800", label: "Confianza media (40–60 %)" },
            { color: "#eab308", label: "Baja confianza (< 40 %)" },
          ] as const).map(item => (
            <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 10, height: 10, background: item.color, flexShrink: 0 }} />
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}

function PipelineStep({ num, title, desc, icon, borderLeft }: {
  num: string; title: string; desc: string; icon: React.ReactNode; borderLeft?: boolean;
}) {
  return (
    <div style={{
      padding: "16px 20px",
      borderLeft: borderLeft ? "1px solid var(--vg-line)" : undefined,
      display: "flex", flexDirection: "column", gap: 7,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{
          width: 30, height: 30, borderRadius: "50%",
          background: "var(--vg-accent-soft)", color: "var(--vg-accent)",
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>{icon}</div>
        <span style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-xl)", letterSpacing: "0.12em" }}>{num}</span>
      </div>
      <div style={{ fontSize: 13.5, fontWeight: 500, letterSpacing: "-0.01em", color: "var(--vg-ink-hi)" }}>
        {title}
      </div>
      <div style={{ fontSize: 11.5, color: "var(--vg-ink-md)", lineHeight: 1.5 }}>
        {desc}
      </div>
    </div>
  );
}

function ViewerToolbar({ zoom, hasClose, onClose, onZoomIn, onZoomOut, onReset, modeLabel }: {
  zoom: number; hasClose?: boolean; onClose?: () => void;
  onZoomIn: () => void; onZoomOut: () => void; onReset: () => void;
  modeLabel?: string;
}) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "0 16px",
      height: 38, background: "var(--vg-panel)", borderBottom: "1px solid var(--vg-line)", flexShrink: 0,
    }}>
      {modeLabel && (
        <span style={{ fontFamily: "var(--vg-mono)", fontSize: 11, color: "var(--vg-accent)", letterSpacing: "0.06em" }}>{modeLabel}</span>
      )}
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 2 }}>
        <button className="btn-icon" onClick={onZoomOut} title="Alejar"><ZoomOutIcon /></button>
        <button className="btn-icon" onClick={onZoomIn} title="Acercar"><ZoomInIcon /></button>
        <button className="btn-icon" onClick={onReset} title="Restablecer vista"><ResetViewIcon /></button>
        <span style={{ fontFamily: "var(--vg-mono)", fontSize: 11, color: "var(--vg-ink-lo)", width: 44, textAlign: "center" }}>
          {Math.round(zoom * 100)}%
        </span>
        {hasClose && (
          <>
            <span style={{ width: 1, height: 16, background: "var(--vg-line)", margin: "0 6px" }} />
            <button className="btn btn-quiet" style={{ gap: 6, height: 26, fontSize: 12, padding: "0 10px" }} onClick={onClose}>
              <CloseIcon /> Cerrar
            </button>
          </>
        )}
      </div>
    </div>
  );
}
