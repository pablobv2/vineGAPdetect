import { useEffect, useMemo, useRef, useState } from "react";
import { exportDetectionsGpkg } from "../api/client";
import type { DetectionItem, ImageMeta } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useDashboardStateContext } from "../hooks/DashboardStateContext";
import { generatePdfReport } from "../utils/exportPdf";
import { consumePendingHistoryRestore } from "../utils/historyRestoreStore";
import type { InferenceCanvasHandle } from "./InferenceCanvas";
import { TopBar } from "./dashboard/TopBar";
import { ModeTabs } from "./dashboard/ModeTabs";
import { LeftRail } from "./dashboard/LeftRail";
import { CenterViewer } from "./dashboard/CenterViewer";
import { RightPanel } from "./dashboard/RightPanel";

function longestPolygonSideM(polygon: [number, number][], resolutionX: number, resolutionY: number): number | null {
  if (!Array.isArray(polygon) || polygon.length < 2) return null;
  const points = polygon
    .map(point => {
      const x = Number(point[0]);
      const y = Number(point[1]);
      return Number.isFinite(x) && Number.isFinite(y) ? ([x, y] as [number, number]) : null;
    })
    .filter((point): point is [number, number] => point !== null);
  if (points.length < 2) return null;
  if (
    points.length >= 2 &&
    points[0][0] === points[points.length - 1][0] &&
    points[0][1] === points[points.length - 1][1]
  ) {
    points.pop();
  }
  if (points.length < 2) return null;

  const scaleX = Math.abs(resolutionX);
  const scaleY = Math.abs(resolutionY);
  const lengths = points.map(([x1, y1], i) => {
    const [x2, y2] = points[(i + 1) % points.length];
    return Math.hypot((x2 - x1) * scaleX, (y2 - y1) * scaleY);
  }).filter(Number.isFinite);
  return lengths.length ? Math.max(...lengths) : null;
}

function recalculateMissingVines(detection: DetectionItem, imageMeta: ImageMeta | undefined, vineWidth: number): DetectionItem {
  const resolutionX = imageMeta?.resolution_x;
  const resolutionY = imageMeta?.resolution_y;
  if (
    typeof resolutionX !== "number" ||
    typeof resolutionY !== "number" ||
    !Number.isFinite(resolutionX) ||
    !Number.isFinite(resolutionY) ||
    !Number.isFinite(vineWidth) ||
    vineWidth <= 0
  ) {
    return detection;
  }

  const orientedLengthM = detection.obb_polygon
    ? longestPolygonSideM(detection.obb_polygon, resolutionX, resolutionY)
    : null;
  if (orientedLengthM != null) {
    return { ...detection, estimated_missing_vines: Math.max(1, Math.round(orientedLengthM / vineWidth)) };
  }

  const bbox = detection.bbox_xyxy;
  if (!Array.isArray(bbox) || bbox.length < 4) return detection;

  const widthPx = Math.abs(Number(bbox[2]) - Number(bbox[0]));
  const heightPx = Math.abs(Number(bbox[3]) - Number(bbox[1]));
  if (!Number.isFinite(widthPx) || !Number.isFinite(heightPx)) return detection;

  const widthM = widthPx * Math.abs(resolutionX);
  const heightM = heightPx * Math.abs(resolutionY);
  const gapLength = Math.max(widthM, heightM);
  const estimatedMissing = Math.max(1, Math.round(gapLength / vineWidth));
  return { ...detection, estimated_missing_vines: estimatedMissing };
}

/**
* Orquesta el flujo principal: carga de imagen, inferencia, XAI, filtros y exportaciones.
* Conecta el estado global con los paneles visuales, recalcula marras segun el
* ancho de cepa elegido por el usuario y habilita exportacion PDF/GPKG cuando
* existen detecciones y metadatos suficientes.
*/
export function Dashboard() {
  const { user } = useAuth();
  const { state, actions } = useDashboardStateContext();
  const canvasRef = useRef<InferenceCanvasHandle | null>(null);
  const [pdfGenerating, setPdfGenerating] = useState(false);

  useEffect(() => {
    const restore = consumePendingHistoryRestore();
    if (restore) actions.restoreFromHistory(restore);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const canRunAnalysis = (user?.role === "admin" || user?.role === "operator") && !state.isHistoryRestored;
  const canInspectAnalysis = canRunAnalysis || state.isHistoryRestored;
  const displayFilename = state.displayFilename ?? state.uploadedFile?.name;

  const imageMeta = state.inferenceResult?.image_meta;
  const detections = useMemo(
    () => (state.inferenceResult?.detections ?? []).map(detection => recalculateMissingVines(detection, imageMeta, state.vineWidth)),
    [state.inferenceResult?.detections, imageMeta, state.vineWidth],
  );
  const filteredDetections = detections.filter(d => d.confidence >= state.confThreshold);

  const inferenceResults = state.inferenceDone && state.inferenceResult ? {
    detectionCount: filteredDetections.length,
    meanConfidence: filteredDetections.length > 0
      ? filteredDetections.reduce((s, d) => s + d.confidence, 0) / filteredDetections.length
      : 0,
    estimatedMissing: filteredDetections.reduce((s, d) => s + (d.estimated_missing_vines ?? 0), 0),
    inferenceMs: Math.round((state.inferenceResult.summary?.processing_time_seconds ?? 0) * 1000),
  } : null;

  const showRightPanel = state.viewMode === "inference" || state.viewMode === "xai";

  const canExportGpkg = Boolean(
    filteredDetections.length &&
    imageMeta?.crs &&
    Array.isArray(imageMeta?.transform) &&
    imageMeta!.transform!.length === 6,
  );

  const handleExportGPKG = async () => {
    if (!filteredDetections.length) return;
    if (!imageMeta?.crs || !imageMeta?.transform || imageMeta.transform.length !== 6) {
      actions.setApiError(
        "Solo puede exportarse a GeoPackage si el ortomosaico es un GeoTIFF con CRS y georreferenciación.",
      );
      return;
    }
    try {
      const parcelName = displayFilename?.replace(/\.[^.]+$/, "") ?? "marras";
      const blob = await exportDetectionsGpkg({
        detections: filteredDetections.map(d => ({
          id: d.id,
          class_name: d.class_name ?? "marra",
          confidence: d.confidence,
          obb_polygon: (d.obb_polygon as unknown as number[][])
            ?? (d.bbox_xyxy
              ? [
                [d.bbox_xyxy[0], d.bbox_xyxy[1]],
                [d.bbox_xyxy[2], d.bbox_xyxy[1]],
                [d.bbox_xyxy[2], d.bbox_xyxy[3]],
                [d.bbox_xyxy[0], d.bbox_xyxy[3]],
              ]
              : []),
          estimated_missing_vines: d.estimated_missing_vines ?? 0,
        })),
        transform: imageMeta.transform,
        crs: imageMeta.crs,
        parcelName,
        confThreshold: state.confThreshold,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${parcelName}_marras.gpkg`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      actions.setApiError(
        err instanceof Error ? err.message : "No se pudo generar el GeoPackage.",
      );
    }
  };

  const handleExportPDF = async () => {
    if (!inferenceResults || pdfGenerating) return;
    setPdfGenerating(true);
    try {
      await generatePdfReport({
        fileName: displayFilename ?? "análisis",
        parcelMeta: state.parcelMeta,
        detections: filteredDetections,
        metrics: inferenceResults,
        imageUrl: state.imageUrl,
        confThreshold: state.confThreshold,
      });
    } catch {
      actions.setApiError("No se pudo generar el informe PDF.");
    } finally {
      setPdfGenerating(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <TopBar project={displayFilename?.replace(/\.[^.]+$/, "") ?? undefined} />

      {/* Error banner */}
      {state.apiError && (
        <div style={{
          padding: "10px 20px", background: "color-mix(in srgb, #c0392b 15%, var(--vg-bg))",
          borderBottom: "1px solid #c0392b", color: "#c0392b", fontSize: 13,
          display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0,
        }}>
          <span>{state.apiError}</span>
          <button
            onClick={() => actions.setApiError("")}
            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
          >
            ×
          </button>
        </div>
      )}

      {state.isHistoryRestored && (
        <div style={{
          padding: "9px 20px",
          background: "color-mix(in srgb, var(--vg-accent) 12%, var(--vg-bg))",
          borderBottom: "1px solid var(--vg-line)",
          color: "var(--vg-ink-hi)",
          fontSize: 12,
          flexShrink: 0,
        }}>
          Análisis restaurado desde Mis parcelas. La detección se muestra con los resultados guardados; XAI se regenera desde el GeoTIFF conservado.
        </div>
      )}

      {state.imageUrl && (
        <ModeTabs
          active={state.viewMode}
          canRunAnalysis={canInspectAnalysis}
          hasImage={Boolean(state.imageUrl)}
          onChange={actions.handleViewModeChange}
        />
      )}

      {/* Body */}
      <div style={{ flex: 1, display: "flex", minHeight: 0, overflow: "hidden" }}>
        <LeftRail
          viewMode={state.viewMode}
          uploadedFile={state.uploadedFile}
          displayFilename={displayFilename}
          isHistoryRestored={state.isHistoryRestored}
          parcelMeta={state.parcelMeta}
          canRunAnalysis={canRunAnalysis}
          confThreshold={state.confThreshold}
          vineWidth={state.vineWidth}
          inferenceRunning={state.inferenceRunning}
          inferenceDone={state.inferenceDone}
          showInferenceLabels={state.showInferenceLabels}
          historyId={state.historyId}
          isSaved={state.isSaved}
          savingParcel={state.savingParcel}
          xaiOpacity={state.xaiOpacity}
          xaiShowDetections={state.xaiShowDetections}
          xaiRunning={state.xaiRunning}
          onSetConfThreshold={actions.setConfThreshold}
          onSetVineWidth={actions.setVineWidth}
          onToggleLabels={() => actions.setShowInferenceLabels(!state.showInferenceLabels)}
          onRunInference={actions.runInference}
          onSaveParcel={actions.saveParcel}
          onXaiOpacityChange={actions.setXaiOpacity}
          onToggleXaiDetections={() => actions.setXaiShowDetections(!state.xaiShowDetections)}
        />

        <CenterViewer
          viewMode={state.viewMode}
          imageUrl={state.imageUrl}
          isHistoryRestored={state.isHistoryRestored}
          previewLoading={state.previewLoading}
          detections={filteredDetections}
          sourceWidth={state.parcelMeta?.sourceWidth}
          sourceHeight={state.parcelMeta?.sourceHeight}
          showInferenceLabels={state.showInferenceLabels}
          inferenceRunning={state.inferenceRunning}
          inferenceDone={state.inferenceDone}
          inferenceProgress={state.inferenceProgress}
          xaiRunning={state.xaiRunning}
          xaiDone={state.xaiDone}
          xaiScope={state.xaiScope}
          xaiDataUrl={state.xaiDataUrl}
          xaiOverlayDataUrl={state.xaiOverlayDataUrl}
          xaiResult={state.xaiResult}
          xaiOpacity={state.xaiOpacity}
          xaiShowDetections={state.xaiShowDetections}
          zoom={state.zoom}
          visibleFeatureCount={state.visibleFeatureCount}
          canvasRef={canvasRef}
          onFileProcess={actions.processFile}
          onClose={actions.closeFile}
          onZoomChange={actions.setZoom}
          onFeatureCountChange={actions.setVisibleFeatureCount}
        />

        {showRightPanel && (
          <RightPanel
            viewMode={state.viewMode as "inference" | "xai"}
            results={inferenceResults}
            detections={detections}
            confThreshold={state.confThreshold}
            xaiDetectionId={state.xaiDetectionId}
            xaiScope={state.xaiScope}
            xaiConfThreshold={state.xaiConfThreshold}
            xaiResult={state.xaiResult}
            isHistoryRestored={state.isHistoryRestored}
            canExportGpkg={canExportGpkg}
            onExportGPKG={() => void handleExportGPKG()}
            onExportPDF={() => void handleExportPDF()}
            pdfGenerating={pdfGenerating}
          />
        )}
      </div>
    </div>
  );
}
