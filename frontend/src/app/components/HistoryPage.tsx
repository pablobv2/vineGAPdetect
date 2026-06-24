import { useMemo, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { deleteHistoryItem, getHistory, getHistoryItem, getQuota } from "../api/client";
import type { AnalysisHistoryItem, InferenceResult, QuotaResponse } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import type { HistoryRestoreData } from "../hooks/useDashboardState";
import { setPendingHistoryRestore } from "../utils/historyRestoreStore";
import { TopBar } from "./dashboard/TopBar";

function fmt(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });
}

function pct(v: number | null): string {
  return v != null ? `${(v * 100).toFixed(1)} %` : "—";
}

function getImageDimensions(src: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => reject(new Error("No se pudieron leer las dimensiones de la previsualización."));
    img.src = src;
  });
}

type SortCol = "filename" | "executed_at" | "detection_count" | "mean_confidence" | "estimated_missing";
type SortDir = "asc" | "desc";

function sortRows(rows: AnalysisHistoryItem[], col: SortCol, dir: SortDir): AnalysisHistoryItem[] {
  return [...rows].sort((a, b) => {
    const av = a[col] ?? "";
    const bv = b[col] ?? "";
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return dir === "asc" ? cmp : -cmp;
  });
}

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function HistoryPage() {
  const { status, user } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState<AnalysisHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [sortCol, setSortCol] = useState<SortCol>("executed_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [quota, setQuota] = useState<QuotaResponse | null>(null);

  useEffect(() => {
    if (status === "anonymous") { void navigate("/", { replace: true }); return; }
    if (status !== "authenticated") return;
    setLoading(true);
    Promise.all([
      getHistory(),
      getQuota(),
    ])
      .then(([items, q]) => { setRows(items); setQuota(q); })
      .catch(e => setError(e instanceof Error ? e.message : "Error al cargar las parcelas."))
      .finally(() => setLoading(false));
  }, [status, navigate]);

  const sorted = useMemo(() => sortRows(rows, sortCol, sortDir), [rows, sortCol, sortDir]);

  const handleSort = (col: SortCol) => {
    if (col === sortCol) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };

  const handleRowClick = async (row: AnalysisHistoryItem) => {
    if (loadingId || deletingId) return;
    setLoadingId(row.id);
    try {
      const detail = await getHistoryItem(row.id);
      if (!detail.result_json || !detail.preview_png_b64) {
        setError("Este registro no tiene datos de inferencia almacenados (se ejecutó antes de esta versión).");
        return;
      }
      const inferenceResult = JSON.parse(detail.result_json) as InferenceResult;
      const imageMeta = inferenceResult.image_meta;
      const sourceWidth = detail.source_width ?? imageMeta.width;
      const sourceHeight = detail.source_height ?? imageMeta.height;
      const imageUrl = `data:image/jpeg;base64,${detail.preview_png_b64}`;
      const previewDims = await getImageDimensions(imageUrl);
      const previewScaleX = sourceWidth > 0 ? previewDims.width / sourceWidth : 1;
      const previewScaleY = sourceHeight > 0 ? previewDims.height / sourceHeight : 1;
      const previewScale = Math.min(previewScaleX, previewScaleY);
      inferenceResult.image_meta = {
        ...imageMeta,
        width: sourceWidth,
        height: sourceHeight,
        file_type: detail.file_type ?? imageMeta.file_type,
        resolution_x: detail.resolution_x ?? imageMeta.resolution_x,
        resolution_y: detail.resolution_y ?? imageMeta.resolution_y,
        resolution_unit: detail.resolution_unit ?? imageMeta.resolution_unit,
        crs: detail.crs ?? imageMeta.crs ?? null,
        transform: detail.transform ?? imageMeta.transform ?? null,
        parcel_area_hectares: detail.parcel_area_hectares ?? imageMeta.parcel_area_hectares ?? null,
        location_center_lat: detail.location_center_lat ?? imageMeta.location_center_lat ?? null,
        location_center_lon: detail.location_center_lon ?? imageMeta.location_center_lon ?? null,
        acquisition_date: detail.acquisition_date ?? imageMeta.acquisition_date ?? null,
      };
      const restore: HistoryRestoreData = {
        historyId: detail.id,
        hasSourceArtifact: Boolean(detail.has_source_artifact),
        imageUrl,
        filename: detail.original_filename ?? detail.filename ?? row.filename,
        parcelMeta: {
          sourceWidth,
          sourceHeight,
          previewWidth: previewDims.width,
          previewHeight: previewDims.height,
          fileType: detail.file_type ?? imageMeta.file_type,
          resolutionX: detail.resolution_x ?? imageMeta.resolution_x,
          resolutionY: detail.resolution_y ?? imageMeta.resolution_y,
          resolutionUnit: detail.resolution_unit ?? imageMeta.resolution_unit ?? null,
          crs: detail.crs ?? imageMeta.crs ?? null,
          areaHectares: detail.parcel_area_hectares ?? imageMeta.parcel_area_hectares ?? null,
          centerLat: detail.location_center_lat ?? imageMeta.location_center_lat ?? null,
          centerLon: detail.location_center_lon ?? imageMeta.location_center_lon ?? null,
          acquisitionDate: detail.acquisition_date ?? imageMeta.acquisition_date ?? null,
          previewScale,
          previewScaleX,
          previewScaleY,
        },
        inferenceResult,
      };
      setPendingHistoryRestore(restore);
      void navigate("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar el análisis.");
    } finally {
      setLoadingId(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, row: AnalysisHistoryItem) => {
    e.stopPropagation();
    if (loadingId || deletingId) return;
    setDeletingId(row.id);
    try {
      await deleteHistoryItem(row.id);
      setRows(prev => prev.filter(r => r.id !== row.id));
      getQuota().then(setQuota).catch(() => undefined);
    } catch (err) {
      // 404 means the row is already gone — remove from UI anyway
      if (err instanceof Error && err.message.includes("404")) {
        setRows(prev => prev.filter(r => r.id !== row.id));
      } else {
        setError(err instanceof Error ? err.message : "No se pudo eliminar el registro.");
      }
    } finally {
      setDeletingId(null);
    }
  };

  if (status === "loading") return (
    <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--vg-bg)" }}>
      <div className="spinner" />
    </div>
  );
  if (status !== "authenticated") return null;

  const isAdmin = user?.role === "admin";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", background: "var(--vg-bg)" }}>
      <TopBar />

      <div style={{ flex: 1, overflowY: "auto", padding: "32px 40px" }}>
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ fontSize: 22, fontWeight: 600, color: "var(--vg-ink-hi)", marginBottom: 4 }}>
            Mis parcelas
          </h1>
          <p style={{ fontSize: 13, color: "var(--vg-ink-lo)", marginBottom: 16 }}>
            {isAdmin
              ? "Todas las parcelas guardadas en el sistema."
              : "Tus parcelas guardadas. Guarda una parcela desde el dashboard tras ejecutar la inferencia."}{" "}
            Haz clic en una fila para restaurar el análisis en el visualizador.
          </p>
          {quota && !isAdmin && (
            <div style={{ maxWidth: 440 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--vg-ink-lo)", marginBottom: 6 }}>
                <span>Almacenamiento</span>
                <span style={{ fontFamily: "var(--vg-mono)" }}>
                  {fmtBytes(quota.used_bytes)} de {fmtBytes(quota.total_bytes)}
                </span>
              </div>
              <div style={{ height: 6, background: "var(--vg-line)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{
                  height: "100%",
                  width: `${Math.min(100, (quota.used_bytes / quota.total_bytes) * 100)}%`,
                  background: quota.used_bytes / quota.total_bytes > 0.9 ? "#c0392b" : "var(--vg-accent)",
                  transition: "width 0.3s",
                }} />
              </div>
            </div>
          )}
        </div>

        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 12, color: "var(--vg-ink-lo)", fontSize: 13 }}>
            <div className="spinner" style={{ width: 16, height: 16 }} />
            Cargando parcelas…
          </div>
        )}

        {error && (
          <div
            style={{ padding: "12px 16px", background: "color-mix(in srgb, #c0392b 12%, var(--vg-bg))", border: "1px solid #c0392b", color: "#c0392b", fontSize: 13, borderRadius: 2, marginBottom: 16, cursor: "pointer" }}
            onClick={() => setError(null)}
            title="Haz clic para cerrar"
          >
            {error}
          </div>
        )}

        {!loading && !error && rows.length === 0 && (
          <div style={{ padding: "40px 0", color: "var(--vg-ink-lo)", fontSize: 13, textAlign: "center" }}>
            No hay parcelas guardadas todavía. Ejecuta una inferencia y pulsa "Guardar parcela" en el dashboard.
          </div>
        )}

        {!loading && sorted.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--vg-line)" }}>
                  {isAdmin && <Th>Usuario</Th>}
                  <SortTh col="filename" active={sortCol} dir={sortDir} onSort={handleSort}>Archivo</SortTh>
                  <SortTh col="executed_at" active={sortCol} dir={sortDir} onSort={handleSort} align="right">Fecha</SortTh>
                  <SortTh col="detection_count" active={sortCol} dir={sortDir} onSort={handleSort} align="right">Huecos visibles</SortTh>
                  <SortTh col="mean_confidence" active={sortCol} dir={sortDir} onSort={handleSort} align="right">Confianza media</SortTh>
                  <SortTh col="estimated_missing" active={sortCol} dir={sortDir} onSort={handleSort} align="right">Marras est.</SortTh>
                  <th style={{ width: 40 }} />
                </tr>
              </thead>
              <tbody>
                {sorted.map((r, i) => {
                  const isLoading = loadingId === r.id;
                  const isDeleting = deletingId === r.id;
                  const busy = Boolean(loadingId || deletingId);
                  return (
                    <tr
                      key={r.id}
                      onClick={() => !busy && void handleRowClick(r)}
                      style={{
                        borderBottom: "1px solid var(--vg-line-soft)",
                        background: i % 2 === 0 ? "transparent" : "color-mix(in srgb, var(--vg-line) 10%, transparent)",
                        cursor: busy ? "wait" : "pointer",
                        opacity: isDeleting ? 0.4 : 1,
                        transition: "background 0.1s, opacity 0.15s",
                      }}
                      onMouseEnter={e => { if (!isDeleting) (e.currentTarget as HTMLTableRowElement).style.background = "color-mix(in srgb, var(--vg-accent) 8%, transparent)"; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLTableRowElement).style.background = i % 2 === 0 ? "transparent" : "color-mix(in srgb, var(--vg-line) 10%, transparent)"; }}
                    >
                      {isAdmin && (
                        <Td>
                          <span style={{ fontFamily: "var(--vg-mono)", fontSize: 11, color: "var(--vg-ink-lo)" }}>
                            {r.username ?? "—"}
                          </span>
                        </Td>
                      )}
                      <Td>
                        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          {isLoading && <span className="spinner" style={{ width: 12, height: 12, flexShrink: 0 }} />}
                          <span style={{ fontFamily: "var(--vg-mono)", fontSize: 11, color: "var(--vg-ink-hi)" }}>
                            {r.filename}
                          </span>
                        </span>
                      </Td>
                      <Td align="right">{fmt(r.executed_at)}</Td>
                      <Td align="right">
                        <span style={{ fontWeight: 600, color: r.detection_count > 0 ? "var(--vg-accent)" : "var(--vg-ink-lo)" }}>
                          {r.detection_count}
                        </span>
                        {r.all_detection_count > r.detection_count && (
                          <span style={{ marginLeft: 6, fontFamily: "var(--vg-mono)", fontSize: 10, color: "var(--vg-ink-lo)" }}>
                            / {r.all_detection_count}
                          </span>
                        )}
                      </Td>
                      <Td align="right">{pct(r.mean_confidence)}</Td>
                      <Td align="right">{r.estimated_missing}</Td>
                      <td style={{ padding: "6px 8px", textAlign: "center", verticalAlign: "middle" }}>
                        <button
                          onClick={e => void handleDelete(e, r)}
                          disabled={busy}
                          title="Eliminar registro"
                          style={{
                            background: "none", border: "none", cursor: busy ? "wait" : "pointer",
                            padding: "3px 5px", borderRadius: 3, lineHeight: 1,
                            color: "var(--vg-ink-lo)", fontSize: 14, opacity: busy ? 0.4 : 1,
                            transition: "color 0.1s, background 0.1s",
                          }}
                          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = "#c0392b"; (e.currentTarget as HTMLButtonElement).style.background = "color-mix(in srgb, #c0392b 10%, transparent)"; }}
                          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = "var(--vg-ink-lo)"; (e.currentTarget as HTMLButtonElement).style.background = "none"; }}
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p style={{ marginTop: 16, fontSize: 11, color: "var(--vg-ink-lo)", fontFamily: "var(--vg-mono)" }}>
              {sorted.length} {sorted.length === 1 ? "registro" : "registros"}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th style={{
      padding: "8px 12px", textAlign: "left",
      fontFamily: "var(--vg-mono)", fontSize: 10, letterSpacing: "0.08em",
      textTransform: "uppercase", color: "var(--vg-ink-lo)", fontWeight: 500,
    }}>
      {children}
    </th>
  );
}

function SortTh({ children, col, active, dir, onSort, align }: {
  children: React.ReactNode;
  col: SortCol;
  active: SortCol;
  dir: SortDir;
  onSort: (col: SortCol) => void;
  align?: "right";
}) {
  const isActive = col === active;
  return (
    <th
      onClick={() => onSort(col)}
      style={{
        padding: "8px 12px", textAlign: align ?? "left",
        fontFamily: "var(--vg-mono)", fontSize: 10, letterSpacing: "0.08em",
        textTransform: "uppercase", fontWeight: 500,
        color: isActive ? "var(--vg-ink-hi)" : "var(--vg-ink-lo)",
        cursor: "pointer", userSelect: "none", whiteSpace: "nowrap",
        transition: "color 0.1s",
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLTableCellElement).style.color = "var(--vg-ink-hi)"; }}
      onMouseLeave={e => { (e.currentTarget as HTMLTableCellElement).style.color = isActive ? "var(--vg-ink-hi)" : "var(--vg-ink-lo)"; }}
    >
      {children}
      {" "}
      <span style={{ fontSize: 9, opacity: isActive ? 1 : 0.3 }}>
        {isActive ? (dir === "asc" ? "▲" : "▼") : "▲"}
      </span>
    </th>
  );
}

function Td({ children, align, lo }: { children: React.ReactNode; align?: "right"; lo?: boolean }) {
  return (
    <td style={{
      padding: "9px 12px", textAlign: align ?? "left",
      color: lo ? "var(--vg-ink-lo)" : "var(--vg-ink-hi)",
      verticalAlign: "middle",
    }}>
      {children}
    </td>
  );
}
