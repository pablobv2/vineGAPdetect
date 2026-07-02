import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createHistoryXaiJob, createInferenceJob, createXaiJob, generatePreview, saveParcel as saveParcelApi } from "../api/client";
import type { DetectionItem, InferenceResult, XAIResult } from "../api/types";
import { toDataUrl } from "../api/types";
import { useJobPolling } from "./useJobPolling";

export type ViewMode = "preview" | "inference" | "xai";
export type XAIMethod = "eigencam";
export type XAIScope = "full";

export function getDefaultXaiLayers(): number[] { return [18]; }

export type ParcelMetadata = {
  sourceWidth?: number; sourceHeight?: number;
  previewWidth?: number; previewHeight?: number;
  resolutionX?: number; resolutionY?: number; resolutionUnit?: string | null;
  crs?: string | null; areaHectares?: number | null;
  centerLat?: number | null; centerLon?: number | null;
  acquisitionDate?: string | null; fileType?: string;
  /** Scale factor from original image -> stored preview (set only when restored from history). */
  previewScale?: number;
  previewScaleX?: number;
  previewScaleY?: number;
};

export type HistoryRestoreData = {
  historyId: number;
  hasSourceArtifact?: boolean;
  imageUrl: string;        // data:image/jpeg;base64,... of the stored preview
  parcelMeta: ParcelMetadata;
  inferenceResult: InferenceResult;
  filename: string;        // original filename (used as display label only)
};

function base64DataUrlToFile(dataUrl: string, filename: string): File {
  const [, b64] = dataUrl.split(",");
  const binaryStr = atob(b64);
  const bytes = new Uint8Array(binaryStr.length);
  for (let i = 0; i < binaryStr.length; i++) bytes[i] = binaryStr.charCodeAt(i);
  return new File([bytes], filename, { type: "image/jpeg" });
}

function getImageDimensions(src: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => reject(new Error("No se pudieron leer las dimensiones de la previsualización."));
    img.src = src;
  });
}

export function useDashboardState() {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [displayFilename, setDisplayFilename] = useState<string | null>(null);
  const [isHistoryRestored, setIsHistoryRestored] = useState(false);
  const [historyId, setHistoryId] = useState<number | null>(null);
  const [historyHasSourceArtifact, setHistoryHasSourceArtifact] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode | null>(null);
  const [apiError, setApiError] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [parcelMeta, setParcelMeta] = useState<ParcelMetadata | null>(null);

  const [zoom, setZoom] = useState(1);
  const [visibleFeatureCount, setVisibleFeatureCount] = useState(0);

  const [confThreshold, setConfThreshold] = useState(0.55);
  const [vineWidth, setVineWidth] = useState(1.5);

  const [inferenceRunning, setInferenceRunning] = useState(false);
  const [inferenceDone, setInferenceDone] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [savingParcel, setSavingParcel] = useState(false);
  const [showInferenceLabels, setShowInferenceLabels] = useState(true);
  const [inferenceProgress, setInferenceProgress] = useState(0);
  const [inferenceJobId, setInferenceJobId] = useState<string | null>(null);
  const [inferenceResult, setInferenceResult] = useState<InferenceResult | null>(null);

  const [xaiMethod] = useState<XAIMethod>("eigencam");
  const [xaiScope] = useState<XAIScope>("full");
  const [xaiConfThreshold, setXaiConfThreshold] = useState(0.55);
  const [xaiOpacity, setXaiOpacity] = useState(0.6);
  const [xaiShowDetections, setXaiShowDetections] = useState(true);
  const [xaiDetectionId, setXaiDetectionId] = useState<number | null>(null);
  const [xaiRunning, setXAIRunning] = useState(false);
  const [xaiDone, setXAIDone] = useState(false);
  const [xaiJobId, setXaiJobId] = useState<string | null>(null);
  const [xaiResult, setXAIResult] = useState<XAIResult | null>(null);

  const objectUrlRef = useRef<string | null>(null);
  const previewRequestRef = useRef(0);
  const xaiThresholdChangePendingRef = useRef(false);

  const inferencePolling = useJobPolling<InferenceResult>(inferenceJobId, Boolean(inferenceJobId));
  const xaiPolling = useJobPolling<XAIResult>(xaiJobId, Boolean(xaiJobId));

  useEffect(() => {
    if (inferencePolling.error) { setApiError(inferencePolling.error); setInferenceRunning(false); setInferenceJobId(null); }
  }, [inferencePolling.error]);

  useEffect(() => {
    const job = inferencePolling.job;
    if (!job) return;
    setInferenceProgress(job.progress ?? 0);
    if (job.status === "running" || job.status === "queued") { setInferenceRunning(true); return; }
    if (job.status === "failed") { setInferenceRunning(false); setInferenceDone(false); setInferenceJobId(null); setApiError(job.error ?? "Error ejecutando inferencia"); return; }
    if (job.status === "completed") {
      const result = job.result ?? null;
      setInferenceRunning(false); setInferenceDone(true); setInferenceProgress(100); setInferenceJobId(null);
      setInferenceResult(result);
      setHistoryId(result?.history_id ?? null);
      setIsSaved(false);
      setViewMode("inference");
      // Sync parcelMeta dimensions with the image that was actually inferred.
      // After a history restore, parcelMeta still holds the original GeoTIFF dimensions
      // (e.g. 5000×3000) but the re-run used the 800px preview. Without this update the
      // canvas scales the new detection coordinates as if they were in original space,
      // placing every box in the top-left corner.
      if (result?.image_meta) {
        const { width, height } = result.image_meta;
        setParcelMeta(prev => {
          if (!prev) return prev;
          if (prev.sourceWidth === width && prev.sourceHeight === height) return prev;
          return { ...prev, sourceWidth: width, sourceHeight: height, previewScale: undefined };
        });
      }
    }
  }, [inferencePolling.job]);

  useEffect(() => {
    if (xaiPolling.error) { setApiError(xaiPolling.error); setXAIRunning(false); setXaiJobId(null); }
  }, [xaiPolling.error]);

  useEffect(() => {
    const job = xaiPolling.job;
    if (!job) return;
    if (job.status === "running" || job.status === "queued") { setXAIRunning(true); return; }
    if (job.status === "failed") { setXAIRunning(false); setXAIDone(false); setXaiJobId(null); setApiError(job.error ?? "Error generando XAI"); return; }
    if (job.status === "completed") { setXAIRunning(false); setXAIDone(true); setXaiJobId(null); setXAIResult(job.result ?? null); }
  }, [xaiPolling.job]);

  const xaiDataUrl = useMemo(() => {
    if (!xaiResult) return null;
    return toDataUrl(xaiResult.combined_png_base64);
  }, [xaiResult]);
  const xaiOverlayDataUrl = useMemo(() => {
    if (!xaiResult?.overlay_png_base64) return null;
    return toDataUrl(xaiResult.overlay_png_base64);
  }, [xaiResult]);

  const clearObjectUrl = useCallback(() => {
    if (objectUrlRef.current) { URL.revokeObjectURL(objectUrlRef.current); objectUrlRef.current = null; }
  }, []);

  useEffect(() => { return () => clearObjectUrl(); }, [clearObjectUrl]);

  const processFile = async (file: File) => {
    const requestId = ++previewRequestRef.current;
    setApiError("");
    setPreviewLoading(true);
    setUploadedFile(file);
    setDisplayFilename(file.name);
    setIsHistoryRestored(false);
    setHistoryId(null);
    setHistoryHasSourceArtifact(false);
    setIsSaved(false);
    setSavingParcel(false);
    setViewMode("preview");
    setZoom(1);
    setInferenceDone(false); setInferenceRunning(false); setVisibleFeatureCount(0);
    setInferenceProgress(0); setInferenceJobId(null); setInferenceResult(null);
    setXAIDone(false); setXAIRunning(false); setXaiJobId(null); setXAIResult(null);
    setXaiDetectionId(null); setXaiConfThreshold(0.55); setXaiShowDetections(true); setParcelMeta(null);
    try {
      if (file.type === "image/tiff" || /\.tiff?$/i.test(file.name)) {
        clearObjectUrl();
        const preview = await generatePreview(file);
        if (requestId !== previewRequestRef.current) return;
        setImageUrl(toDataUrl(preview.preview_png_base64));
        setParcelMeta({
          sourceWidth: preview.source_width, sourceHeight: preview.source_height,
          resolutionX: preview.resolution_x, resolutionY: preview.resolution_y,
          resolutionUnit: preview.resolution_unit, crs: preview.crs,
          areaHectares: preview.parcel_area_hectares, centerLat: preview.location_center_lat,
          centerLon: preview.location_center_lon, acquisitionDate: preview.acquisition_date,
          fileType: preview.file_type,
        });
      } else {
        clearObjectUrl();
        const objectUrl = URL.createObjectURL(file);
        if (requestId !== previewRequestRef.current) { URL.revokeObjectURL(objectUrl); return; }
        objectUrlRef.current = objectUrl;
        setImageUrl(objectUrl);
        setParcelMeta({ fileType: file.type || "image" });
      }
    } catch (error) {
      if (requestId !== previewRequestRef.current) return;
      setImageUrl(null); setViewMode(null);
      setApiError(error instanceof Error ? error.message : "No se pudo generar la vista previa");
    } finally {
      if (requestId !== previewRequestRef.current) return;
      setPreviewLoading(false);
    }
  };

  const runInference = async () => {
    if (!uploadedFile) return;
    if (isHistoryRestored) {
      setApiError("El análisis restaurado usa una previsualización guardada. Cargue de nuevo el GeoTIFF original para reejecutar la inferencia.");
      return;
    }
    setApiError(""); setInferenceJobId(null); setInferenceRunning(true);
    setInferenceDone(false); setVisibleFeatureCount(0); setInferenceProgress(0); setInferenceResult(null);
    setHistoryId(null); setIsSaved(false);
    try {
      // Use a low capture threshold so all detections are returned.
      // The display threshold (confThreshold) filters client-side via filteredDetections.
      const job = await createInferenceJob(uploadedFile, { confidenceThreshold: 0.05, displayConfidenceThreshold: confThreshold, overlapRatio: 0.25, sliceSize: 640, vineWidth });
      setInferenceJobId(job.job_id);
    } catch (error) {
      setInferenceRunning(false);
      setApiError(error instanceof Error ? error.message : "Error creando job de inferencia");
    }
  };

  const runXAI = async (options?: { confThreshold?: number }) => {
    if (!uploadedFile) return;
    setApiError(""); setXaiJobId(null); setXAIRunning(true); setXAIDone(false); setXAIResult(null);
    try {
      const confThresholdToUse = options?.confThreshold ?? xaiConfThreshold;

      if (isHistoryRestored) {
        if (!historyId || !historyHasSourceArtifact) {
          setXAIRunning(false);
          setXAIDone(Boolean(xaiResult));
          return;
        }
        const job = await createHistoryXaiJob(historyId, {
          method: "eigencam",
          scope: "full",
          detectionId: null,
          targetLayers: getDefaultXaiLayers(),
          confThreshold: confThresholdToUse,
          imgsz: 640,
        });
        setXaiJobId(job.job_id);
        return;
      }

      const job = await createXaiJob(uploadedFile, {
        method: "eigencam",
        scope: "full",
        targetLayers: getDefaultXaiLayers(),
        confThreshold: confThresholdToUse,
        imgsz: 640,
      });
      setXaiJobId(job.job_id);
    } catch (error) {
      setXAIRunning(false);
      setApiError(error instanceof Error ? error.message : "Error creando job XAI");
    }
  };

  useEffect(() => {
    if (!xaiThresholdChangePendingRef.current || isHistoryRestored || viewMode !== "xai" || !uploadedFile) return;
    const timeoutId = window.setTimeout(() => {
      xaiThresholdChangePendingRef.current = false;
      runXAI({ confThreshold: xaiConfThreshold });
    }, 450);
    return () => window.clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [xaiConfThreshold, isHistoryRestored, uploadedFile, viewMode]);

  const restoreFromHistory = useCallback((data: HistoryRestoreData) => {
    previewRequestRef.current += 1;
    clearObjectUrl();
    // Build a local File from the stored preview only for display-oriented browser APIs.
    // The history state blocks re-analysis so this JPEG is never treated as the original GeoTIFF.
    const previewFile = base64DataUrlToFile(data.imageUrl, "history-preview.jpg");
    setUploadedFile(previewFile);
    setDisplayFilename(data.filename);
    setIsHistoryRestored(true);
    setHistoryId(data.historyId);
    setHistoryHasSourceArtifact(Boolean(data.hasSourceArtifact));
    setImageUrl(data.imageUrl);
    setParcelMeta(data.parcelMeta);
    setInferenceResult(data.inferenceResult);
    setInferenceDone(true);
    setInferenceRunning(false);
    setInferenceProgress(100);
    setInferenceJobId(null);
    setViewMode("inference");
    setZoom(1);
    setConfThreshold(data.inferenceResult.parameters?.display_confidence_threshold ?? 0.55);
    setVineWidth(data.inferenceResult.parameters?.typical_vine_width ?? 1.5);
    setXaiConfThreshold(data.inferenceResult.parameters?.display_confidence_threshold ?? 0.55);
    setXaiJobId(null);
    setXaiDetectionId(null);
    setPreviewLoading(false);
    setApiError("");
    setVisibleFeatureCount(0);
    setXAIDone(false);
    setXAIResult(null);
  }, [clearObjectUrl]);

  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode); setZoom(1);
    if (mode === "inference" && !inferenceDone && !inferenceRunning) runInference();
    if (mode === "xai" && !xaiDone && !xaiRunning) runXAI();
  };

  const handleXAIThresholdChange = (value: number) => {
    if (isHistoryRestored) return;
    setXaiConfThreshold(value);
    xaiThresholdChangePendingRef.current = true;
  };

  const closeFile = () => {
    previewRequestRef.current += 1;
    clearObjectUrl(); setZoom(1); setUploadedFile(null); setImageUrl(null);
    setDisplayFilename(null); setIsHistoryRestored(false);
    setHistoryId(null); setHistoryHasSourceArtifact(false);
    setIsSaved(false); setSavingParcel(false);
    setViewMode(null); setPreviewLoading(false); setParcelMeta(null);
    setInferenceResult(null); setXAIResult(null); setXaiShowDetections(true);
    setInferenceJobId(null); setXaiJobId(null); setXaiDetectionId(null);
  };

  const saveParcel = async () => {
    if (!historyId || isSaved || savingParcel) return;
    setSavingParcel(true);
    try {
      await saveParcelApi(historyId);
      setIsSaved(true);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "No se pudo guardar la parcela.");
    } finally {
      setSavingParcel(false);
    }
  };

  return {
    state: {
      uploadedFile, displayFilename, isHistoryRestored, historyId, historyHasSourceArtifact, imageUrl, viewMode, zoom, apiError, previewLoading, parcelMeta,
      confThreshold, vineWidth, inferenceRunning, inferenceDone, showInferenceLabels,
      isSaved, savingParcel,
      visibleFeatureCount, inferenceProgress, inferenceResult,
      xaiMethod, xaiScope, xaiConfThreshold, xaiOpacity, xaiShowDetections, xaiDetectionId,
      xaiRunning, xaiDone, xaiResult, xaiDataUrl, xaiOverlayDataUrl,
    },
    actions: {
      setZoom, setVisibleFeatureCount, setShowInferenceLabels, setApiError,
      setConfThreshold, setVineWidth, setXaiOpacity, setXaiShowDetections,
      processFile, runInference, runXAI, restoreFromHistory, saveParcel,
      handleViewModeChange, handleXAIThresholdChange, closeFile,
    },
  };
}
