import { jsPDF } from "jspdf";
import type { DetectionItem } from "../api/types";
import type { ParcelMetadata } from "../hooks/useDashboardState";

// Brand palette (light theme tokens)
const ACCENT      : [number,number,number] = [110, 138,  62]; // #6E8A3E
const ACCENT_SOFT : [number,number,number] = [230, 237, 210]; // #DDE3C7 approx
const WHITE       : [number,number,number] = [255, 255, 255];
const BG          : [number,number,number] = [242, 239, 231]; // #F2EFE7
const PANEL       : [number,number,number] = [251, 250, 245]; // #FBFAF5
const INK_HI      : [number,number,number] = [ 19,  17,  12]; // #13110C
const INK_LO      : [number,number,number] = [117, 112, 106]; // #75706A
const LINE        : [number,number,number] = [215, 210, 197]; // #D7D2C5

// Confidence colour scale
// Exact same thresholds and hex values as InferenceCanvas.tsx -> getColor().
const CONF_HIGH : [number,number,number] = [255,  51,  51]; // #ff3333 — ≥ 60 %
const CONF_MED  : [number,number,number] = [255, 136,   0]; // #ff8800 — 40–60 %
const CONF_LOW  : [number,number,number] = [234, 179,   8]; // #eab308 — < 40 %

function confColorCSS(confidence: number): string {
  const [r, g, b] = confidence >= 0.6 ? CONF_HIGH : confidence >= 0.4 ? CONF_MED : CONF_LOW;
  return `rgba(${r},${g},${b},0.92)`;
}

function confColorRGB(confidence: number): [number, number, number] {
  return confidence >= 0.6 ? CONF_HIGH : confidence >= 0.4 ? CONF_MED : CONF_LOW;
}

/** Draw detection polygons/boxes over an already-painted canvas, coloured by confidence. */
function drawDetectionsOnCanvas(
  ctx: CanvasRenderingContext2D,
  cw: number,
  ch: number,
  detections: DetectionItem[],
  sourceW: number,
  sourceH: number,
): void {
  const sx = cw / sourceW;
  const sy = ch / sourceH;
  const lw = Math.max(0.8, cw / 500);

  ctx.save();
  ctx.lineWidth = lw;

  for (const det of detections) {
    ctx.strokeStyle = confColorCSS(det.confidence);
    ctx.beginPath();
    if (det.obb_polygon && det.obb_polygon.length >= 3) {
      ctx.moveTo(det.obb_polygon[0][0] * sx, det.obb_polygon[0][1] * sy);
      for (let i = 1; i < det.obb_polygon.length; i++) {
        ctx.lineTo(det.obb_polygon[i][0] * sx, det.obb_polygon[i][1] * sy);
      }
      ctx.closePath();
    } else {
      const [x1, y1, x2, y2] = det.bbox_xyxy;
      ctx.rect(x1 * sx, y1 * sy, (x2 - x1) * sx, (y2 - y1) * sy);
    }
    ctx.stroke();
  }
  ctx.restore();
}

/** Convert any URL (blob:, data:, http:) to a JPEG data URL at a bounded resolution. */
async function prepareImage(
  url: string,
  maxPx = 1400,
  boxes?: { detections: DetectionItem[]; sourceW: number; sourceH: number },
): Promise<{ dataUrl: string; w: number; h: number } | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const scale = Math.min(1, maxPx / Math.max(img.naturalWidth, img.naturalHeight, 1));
      const w = Math.round(img.naturalWidth  * scale);
      const h = Math.round(img.naturalHeight * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) { resolve(null); return; }
      ctx.drawImage(img, 0, 0, w, h);
      if (boxes && boxes.detections.length > 0) {
        const sw = boxes.sourceW || img.naturalWidth;
        const sh = boxes.sourceH || img.naturalHeight;
        drawDetectionsOnCanvas(ctx, w, h, boxes.detections, sw, sh);
      }
      resolve({ dataUrl: canvas.toDataURL("image/jpeg", 0.85), w, h });
    };
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

export interface PdfReportData {
  fileName: string;
  parcelMeta: ParcelMetadata | null;
  detections: DetectionItem[];
  metrics: {
    detectionCount: number;
    meanConfidence: number;
    estimatedMissing: number;
    inferenceMs: number;
  };
  imageUrl: string | null;
  confThreshold: number;
}

export async function generatePdfReport(data: PdfReportData): Promise<void> {
  const { fileName, parcelMeta, detections, metrics, imageUrl, confThreshold } = data;

  const pdf = new jsPDF({ unit: "mm", format: "a4", orientation: "portrait" });
  const W  = 210;
  const ML = 20;
  const CW = W - ML * 2; // 170 mm
  let y    = 0;

  // Helpers
  const sectionLabel = (text: string, yPos: number) => {
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(7);
    pdf.setTextColor(...INK_LO);
    pdf.text(text.toUpperCase(), ML, yPos);
    const lw = pdf.getTextWidth(text.toUpperCase());
    pdf.setDrawColor(...LINE);
    pdf.setLineWidth(0.3);
    pdf.line(ML + lw + 3, yPos - 0.8, ML + CW, yPos - 0.8);
  };

  const newPageIfNeeded = (needed: number) => {
    if (y + needed > 277) { pdf.addPage(); y = 20; }
  };

  // HEADER
  pdf.setFillColor(...ACCENT);
  pdf.rect(0, 0, W, 38, "F");

  pdf.setTextColor(...WHITE);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(20);
  pdf.text("vineGAPdetect", ML, 15);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);
  pdf.text("Sistema de detección de marras en viñedos", ML, 22);

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(12);
  pdf.text("Informe de análisis de marras", ML, 32);

  const now     = new Date();
  const dateStr = now.toLocaleDateString("es-ES", { year: "numeric", month: "long", day: "numeric" });
  const timeStr = now.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(7.5);
  pdf.setTextColor(...WHITE);
  pdf.text(`${dateStr}  ·  ${timeStr}`, W - ML, 32, { align: "right" });

  y = 48;

  // METADATA
  sectionLabel("Información de la parcela", y);
  y += 6;

  const metaRows: [string, string][] = [["Archivo", fileName]];
  if (parcelMeta?.fileType)
    metaRows.push(["Formato", parcelMeta.fileType]);
  if (parcelMeta?.sourceWidth && parcelMeta?.sourceHeight)
    metaRows.push(["Dimensiones", `${parcelMeta.sourceWidth} × ${parcelMeta.sourceHeight} px`]);
  if (parcelMeta?.resolutionX)
    metaRows.push(["GSD", `${parcelMeta.resolutionX.toFixed(4)} ${parcelMeta.resolutionUnit ?? "m"}/px`]);
  if (parcelMeta?.crs)
    metaRows.push(["Sistema de referencia", parcelMeta.crs]);
  if (parcelMeta?.areaHectares != null)
    metaRows.push(["Superficie estimada", `${parcelMeta.areaHectares.toFixed(2)} ha`]);
  if (parcelMeta?.centerLat != null && parcelMeta?.centerLon != null)
    metaRows.push(["Centro de parcela", `${parcelMeta.centerLat.toFixed(5)}°N, ${parcelMeta.centerLon.toFixed(5)}°E`]);
  if (parcelMeta?.acquisitionDate)
    metaRows.push(["Fecha de adquisición", parcelMeta.acquisitionDate]);

  const halfCW    = (CW - 8) / 2;
  const numMDRows = Math.ceil(metaRows.length / 2);

  for (let i = 0; i < metaRows.length; i++) {
    const col  = i % 2;
    const row  = Math.floor(i / 2);
    const xBase = ML + col * (halfCW + 8);
    const yRow  = y + row * 9;

    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(7);
    pdf.setTextColor(...INK_LO);
    pdf.text(metaRows[i][0], xBase, yRow);

    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(8.5);
    pdf.setTextColor(...INK_HI);
    pdf.text(metaRows[i][1], xBase, yRow + 4.5);
  }

  y += numMDRows * 9 + 10;

  // RESULTS SUMMARY
  newPageIfNeeded(42);
  sectionLabel("Resultados del análisis", y);
  y += 5;

  pdf.setFont("helvetica", "italic");
  pdf.setFontSize(7.5);
  pdf.setTextColor(...INK_LO);
  pdf.text(`Umbral de confianza aplicado: ${Math.round(confThreshold * 100)} %`, ML, y);
  y += 5;

  const tiles = [
    { label: ["Huecos", "detectados"],  value: String(metrics.detectionCount),                    accent: true  },
    { label: ["Confianza", "media"],     value: `${(metrics.meanConfidence * 100).toFixed(1)} %`, accent: false },
    { label: ["Marras", "estimadas"],    value: String(metrics.estimatedMissing),                  accent: true  },
  ];
  const tileW = (CW - 2 * 4) / 3;
  const tileH = 22;

  tiles.forEach((tile, i) => {
    const tx = ML + i * (tileW + 4);
    pdf.setFillColor(...(tile.accent ? ACCENT_SOFT : PANEL));
    pdf.rect(tx, y, tileW, tileH, "F");
    pdf.setDrawColor(...LINE);
    pdf.setLineWidth(0.2);
    pdf.rect(tx, y, tileW, tileH, "S");

    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(6.5);
    pdf.setTextColor(...INK_LO);
    tile.label.forEach((line, li) => {
      pdf.text(line, tx + tileW / 2, y + 5 + li * 3.5, { align: "center" });
    });

    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(16);
    pdf.setTextColor(...(tile.accent ? ACCENT : INK_HI));
    pdf.text(tile.value, tx + tileW / 2, y + tileH - 3, { align: "center" });
  });

  y += tileH + 10;

  // PREVIEW IMAGE WITH DETECTIONS
  if (imageUrl) {
    const prepared = await prepareImage(imageUrl, 1400, detections.length > 0 ? {
      detections,
      sourceW: parcelMeta?.sourceWidth ?? 0,
      sourceH: parcelMeta?.sourceHeight ?? 0,
    } : undefined);
    if (prepared) {
      // Fill the rest of the page: reserve space for label (6 mm), gap (4 mm), legend (10 mm).
      const FOOTER_Y      = 288;
      const LEGEND_BLOCK  = 10;
      const GAP_AFTER_IMG = 4;
      const LABEL_H       = 6;
      const availForImg   = Math.max(30, FOOTER_Y - y - LABEL_H - GAP_AFTER_IMG - LEGEND_BLOCK);

      sectionLabel("Ortomosaico analizado", y);
      y += LABEL_H;

      const aspect  = prepared.w / Math.max(prepared.h, 1);
      const pdfImgW = Math.min(CW, availForImg * aspect);
      const pdfImgH = Math.min(availForImg, pdfImgW / aspect);

      const imgX = ML + (CW - pdfImgW) / 2;
      pdf.setDrawColor(...LINE);
      pdf.setLineWidth(0.4);
      pdf.rect(imgX - 0.5, y - 0.5, pdfImgW + 1, pdfImgH + 1, "S");
      pdf.addImage(prepared.dataUrl, "JPEG", imgX, y, pdfImgW, pdfImgH);
      y += pdfImgH + GAP_AFTER_IMG;

      // Confidence legend
      const legendItems: [string, [number,number,number]][] = [
        ["Alta confianza (>= 60 %)",  CONF_HIGH],
        ["Confianza media (40-60 %)", CONF_MED],
        ["Baja confianza (< 40 %)",   CONF_LOW],
      ];
      const swatchSide = 2.8;
      const itemGap    = 57;
      const legendW    = legendItems.length * itemGap - 10;
      let lx           = ML + (CW - legendW) / 2;

      legendItems.forEach(([label, rgb]) => {
        pdf.setFillColor(...rgb);
        pdf.rect(lx, y + 0.3, swatchSide, swatchSide, "F");
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(7);
        pdf.setTextColor(...INK_LO);
        pdf.text(label, lx + swatchSide + 2, y + swatchSide - 0.1);
        lx += itemGap;
      });
    }
  }

  // FOOTER on every page
  const totalPages = pdf.getNumberOfPages();
  for (let p = 1; p <= totalPages; p++) {
    pdf.setPage(p);
    pdf.setFillColor(...LINE);
    pdf.rect(0, 288, W, 9, "F");
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(6.5);
    pdf.setTextColor(...INK_LO);
    pdf.text("vineGAPdetect — Sistema de detección de marras en viñedos", ML, 293.5);
    pdf.text(`Página ${p} / ${totalPages}`, W - ML, 293.5, { align: "right" });
  }

  // SAVE
  const safeName = fileName.replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9_\-]/g, "_");
  pdf.save(`${safeName}_informe_marras.pdf`);
}
