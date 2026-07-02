import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";
import type { EventsKey } from "ol/events";
import Feature from "ol/Feature";
import Map from "ol/Map";
import View from "ol/View";
import Point from "ol/geom/Point";
import Polygon from "ol/geom/Polygon";
import { defaults as defaultInteractions } from "ol/interaction/defaults";
import MouseWheelZoom from "ol/interaction/MouseWheelZoom";
import ImageLayer from "ol/layer/Image";
import VectorLayer from "ol/layer/Vector";
import { unByKey } from "ol/Observable";
import Projection from "ol/proj/Projection";
import Static from "ol/source/ImageStatic";
import VectorSource from "ol/source/Vector";
import { Fill, Stroke, Style, Text } from "ol/style";
import "ol/ol.css";
import type { DetectionItem } from "../api/types";

interface Props {
  imageUrl: string;
  overlayUrl?: string;
  detections: DetectionItem[];
  sourceWidth?: number;
  sourceHeight?: number;
  showCount?: number;
  showLabels?: boolean;
  onScaleChange?: (scale: number) => void;
  onFeatureCountChange?: (count: number) => void;
  overlayOpacity?: number;
}

/** API imperativa usada por la barra de herramientas para controlar zoom y encuadre. */
export interface InferenceCanvasHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  resetView: () => void;
}

function clamp(value: number, min: number, max: number): number { return Math.max(min, Math.min(max, value)); }

function getColor(confidence: number): string {
  if (confidence >= 0.6) return "#ff3333";
  if (confidence >= 0.4) return "#ff8800";
  return "#eab308";
}

function toFiniteNumber(value: unknown): number | null {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function extractBBox(detection: DetectionItem): [number, number, number, number] | null {
  const rawBbox = (detection as { bbox_xyxy?: unknown }).bbox_xyxy;
  if (Array.isArray(rawBbox) && rawBbox.length >= 4) {
    const x1 = toFiniteNumber(rawBbox[0]), y1 = toFiniteNumber(rawBbox[1]);
    const x2 = toFiniteNumber(rawBbox[2]), y2 = toFiniteNumber(rawBbox[3]);
    if (x1 !== null && y1 !== null && x2 !== null && y2 !== null) return [x1, y1, x2, y2];
  }
  const polygon = (detection as { obb_polygon?: unknown }).obb_polygon;
  if (Array.isArray(polygon) && polygon.length >= 2) {
    const points = polygon.map((point) => {
      if (!Array.isArray(point) || point.length < 2) return null;
      const x = toFiniteNumber(point[0]), y = toFiniteNumber(point[1]);
      return x === null || y === null ? null : ([x, y] as [number, number]);
    }).filter((point): point is [number, number] => Boolean(point));
    if (points.length >= 2) {
      const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
      return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    }
  }
  return null;
}

function extractPolygonPoints(detection: DetectionItem): [number, number][] | null {
  const polygon = (detection as { obb_polygon?: unknown }).obb_polygon;
  if (!Array.isArray(polygon) || polygon.length < 3) return null;
  const points = polygon.map((point) => {
    if (!Array.isArray(point) || point.length < 2) return null;
    const x = toFiniteNumber(point[0]), y = toFiniteNumber(point[1]);
    return x === null || y === null ? null : ([x, y] as [number, number]);
  }).filter((point): point is [number, number] => Boolean(point));
  return points.length >= 3 ? points : null;
}

function createDetectionFeature(detection: DetectionItem, imageWidth: number, imageHeight: number, sourceWidth: number, sourceHeight: number): Feature<Polygon> | null {
  const polygonPoints = extractPolygonPoints(detection);
  const parsedBBox = extractBBox(detection);
  if (!polygonPoints && !parsedBBox) return null;

  const allCoords: number[] = [];
  if (polygonPoints) for (const [x, y] of polygonPoints) allCoords.push(x, y);
  if (parsedBBox) allCoords.push(...parsedBBox);
  if (allCoords.length === 0) return null;

  const safeSourceW = Math.max(1, sourceWidth), safeSourceH = Math.max(1, sourceHeight);
  const maxAbsCoord = Math.max(...allCoords.map(v => Math.abs(v)));
  const minCoord = Math.min(...allCoords);
  const sourceMatchesPreview = Math.abs(safeSourceW - imageWidth) <= 2 && Math.abs(safeSourceH - imageHeight) <= 2;
  const isNormalized = maxAbsCoord <= 1.5 && minCoord >= -0.5;

  let scaleX = 1, scaleY = 1;
  if (isNormalized) { scaleX = imageWidth; scaleY = imageHeight; }
  else if (!sourceMatchesPreview) { scaleX = imageWidth / safeSourceW; scaleY = imageHeight / safeSourceH; }

  let ring: [number, number][] = [];
  if (polygonPoints) {
    ring = polygonPoints.map(([x, y]) => [clamp(x * scaleX, 0, imageWidth), clamp(imageHeight - y * scaleY, 0, imageHeight)]);
  } else if (parsedBBox) {
    const [x1, y1, x2, y2] = parsedBBox;
    let left = clamp(Math.min(x1, x2) * scaleX, 0, imageWidth);
    let right = clamp(Math.max(x1, x2) * scaleX, 0, imageWidth);
    let top = clamp(imageHeight - Math.min(y1, y2) * scaleY, 0, imageHeight);
    let bottom = clamp(imageHeight - Math.max(y1, y2) * scaleY, 0, imageHeight);
    const minDisplaySize = 2.0;
    if (Math.abs(right - left) < minDisplaySize) { const cx = (left + right) / 2; left = clamp(cx - minDisplaySize / 2, 0, imageWidth); right = clamp(cx + minDisplaySize / 2, 0, imageWidth); }
    if (Math.abs(top - bottom) < minDisplaySize) { const cy = (top + bottom) / 2; top = clamp(cy + minDisplaySize / 2, 0, imageHeight); bottom = clamp(cy - minDisplaySize / 2, 0, imageHeight); }
    ring = [[left, bottom], [right, bottom], [right, top], [left, top]];
  }

  ring = ring.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
  if (ring.length < 3) return null;
  if (new Set(ring.map(([x, y]) => `${x.toFixed(3)}:${y.toFixed(3)}`)).size < 3) return null;

  const first = ring[0], last = ring[ring.length - 1];
  if (first[0] !== last[0] || first[1] !== last[1]) ring = [...ring, first];

  const xs = ring.map(p => p[0]), ys = ring.map(p => p[1]);
  const labelCoord: [number, number] = [Math.min(...xs), Math.max(...ys)];

  const feature = new Feature({ geometry: new Polygon([ring]) });
  feature.set("confidence", detection.confidence);
  feature.set("color", getColor(detection.confidence));
  feature.set("label", `${(detection.confidence * 100).toFixed(0)}%`);
  feature.set("labelCoord", labelCoord);
  return feature;
}

/**
* Visualiza la imagen analizada, superpone XAI y dibuja detecciones OBB con OpenLayers.
* Crea una proyeccion en coordenadas de pixel, representa la imagen como capa
* estatica, dibuja poligonos o cajas de deteccion y comunica escala y numero
* de entidades visibles al resto del dashboard.
*/
export const InferenceCanvas = forwardRef<InferenceCanvasHandle, Props>(function InferenceCanvas(
  { imageUrl, overlayUrl, detections, sourceWidth, sourceHeight, showCount, showLabels = true, onScaleChange, onFeatureCountChange, overlayOpacity = 0.6 },
  ref,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const viewRef = useRef<View | null>(null);
  const vectorSourceRef = useRef<VectorSource | null>(null);
  const mapExtentRef = useRef<[number, number, number, number] | null>(null);
  const baseResolutionRef = useRef<number>(1);
  const minResolutionRef = useRef<number>(1 / 24);
  const maxResolutionRef = useRef<number>(12);
  const resolutionListenerRef = useRef<EventsKey | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const showLabelsRef = useRef(showLabels);
  const overlayOpacityRef = useRef(overlayOpacity);
  const onScaleChangeRef = useRef(onScaleChange);
  const onFeatureCountChangeRef = useRef(onFeatureCountChange);
  const rebuildFeaturesRef = useRef<() => void>(() => {});

  useEffect(() => { onScaleChangeRef.current = onScaleChange; }, [onScaleChange]);
  useEffect(() => { overlayOpacityRef.current = overlayOpacity; }, [overlayOpacity]);
  useEffect(() => { onFeatureCountChangeRef.current = onFeatureCountChange; }, [onFeatureCountChange]);

  const rebuildFeatures = useCallback(() => {
    const vectorSource = vectorSourceRef.current, extent = mapExtentRef.current;
    if (!vectorSource || !extent) { onFeatureCountChangeRef.current?.(0); return; }
    const imageWidth = extent[2], imageHeight = extent[3];
    const detectionSourceWidth = typeof sourceWidth === "number" && Number.isFinite(sourceWidth) && sourceWidth > 0 ? sourceWidth : imageWidth;
    const detectionSourceHeight = typeof sourceHeight === "number" && Number.isFinite(sourceHeight) && sourceHeight > 0 ? sourceHeight : imageHeight;
    const currentDetections = showCount !== undefined ? detections.slice(0, showCount) : detections;
    vectorSource.clear(true);
    const features = currentDetections.map(d => createDetectionFeature(d, imageWidth, imageHeight, detectionSourceWidth, detectionSourceHeight)).filter((f): f is Feature<Polygon> => Boolean(f));
    vectorSource.addFeatures(features);
    onFeatureCountChangeRef.current?.(features.length);
  }, [detections, showCount, sourceWidth, sourceHeight]);

  useEffect(() => { rebuildFeaturesRef.current = rebuildFeatures; }, [rebuildFeatures]);

  useImperativeHandle(ref, () => ({
    zoomIn: () => { const v = viewRef.current; if (!v) return; const r = v.getResolution(); if (!r) return; v.animate({ resolution: Math.max(minResolutionRef.current, r / 1.25), duration: 120 }); },
    zoomOut: () => { const v = viewRef.current; if (!v) return; const r = v.getResolution(); if (!r) return; v.animate({ resolution: Math.min(maxResolutionRef.current, r * 1.25), duration: 120 }); },
    resetView: () => {
      const map = mapRef.current, view = viewRef.current, extent = mapExtentRef.current;
      if (!map || !view || !extent) return;
      view.fit(extent, { size: map.getSize(), padding: [16, 16, 16, 16], duration: 150 });
      const resolution = view.getResolution(); if (!resolution) return;
      baseResolutionRef.current = resolution;
      minResolutionRef.current = resolution / 24;
      maxResolutionRef.current = resolution * 12;
      onScaleChangeRef.current?.(1);
    },
  }), []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let canceled = false;
    const image = new Image();
    image.crossOrigin = "anonymous";

    const cleanup = () => {
      if (resolutionListenerRef.current) { unByKey(resolutionListenerRef.current); resolutionListenerRef.current = null; }
      if (resizeObserverRef.current) { resizeObserverRef.current.disconnect(); resizeObserverRef.current = null; }
      if (mapRef.current) { mapRef.current.setTarget(undefined); mapRef.current = null; }
      viewRef.current = null; vectorSourceRef.current = null; mapExtentRef.current = null;
    };

    const initializeMap = () => {
      if (canceled) return;
      cleanup();
      const width = image.naturalWidth || 1, height = image.naturalHeight || 1;
      const extent: [number, number, number, number] = [0, 0, width, height];
      const projection = new Projection({ code: `image-static-${width}-${height}-${Date.now()}`, units: "pixels", extent });
      const imageLayer = new ImageLayer({ source: new Static({ url: imageUrl, imageExtent: extent, projection }) });
      const vectorSource = new VectorSource();
      const polygonsLayer = new VectorLayer({
        source: vectorSource,
        style: (feature, resolution) => {
          const confidence = Number(feature.get("confidence") ?? 0);
          const color = String(feature.get("color") ?? getColor(confidence));
          const baseResolution = baseResolutionRef.current || resolution || 1;
          const scale = clamp(baseResolution / Math.max(resolution, 1e-9), 0.2, 20);
          const strokeWidth = clamp(1.1 + Math.sqrt(scale) * 1.1, 1.2, 6);
          return new Style({ stroke: new Stroke({ color, width: strokeWidth }), fill: new Fill({ color: "rgba(0,0,0,0.03)" }) });
        },
      });
      const labelsLayer = new VectorLayer({
        source: vectorSource,
        declutter: true,
        style: (feature, resolution) => {
          if (!showLabelsRef.current) return undefined;
          const label = String(feature.get("label") ?? "");
          const labelCoord = feature.get("labelCoord") as [number, number] | undefined;
          if (!labelCoord) return undefined;
          const baseResolution = baseResolutionRef.current || resolution || 1;
          const scale = clamp(baseResolution / Math.max(resolution, 1e-9), 0.2, 20);
          if (scale < 1.35) return undefined;
          const fontSize = clamp(10 + Math.log2(scale + 1) * 4, 10, 20);
          return new Style({
            geometry: new Point(labelCoord),
            text: new Text({ text: label, font: `500 ${fontSize}px IBM Plex Mono, monospace`, fill: new Fill({ color: "#fff" }), backgroundFill: new Fill({ color: "rgba(0,0,0,0.72)" }), padding: [3, 6, 3, 6], textAlign: "left", offsetY: -10, overflow: false }),
          });
        },
      });
      const view = new View({ projection, center: [width / 2, height / 2], zoom: 1, constrainOnlyCenter: false, smoothExtentConstraint: true, extent, showFullExtent: true });
      const layers: any[] = [imageLayer, polygonsLayer, labelsLayer];
      let overlayLayer: ImageLayer<Static> | null = null;
      if (overlayUrl) {
        overlayLayer = new ImageLayer({ source: new Static({ url: overlayUrl, imageExtent: extent, projection }), opacity: overlayOpacityRef.current });
        layers.splice(1, 0, overlayLayer);
      }
      const map = new Map({
        target: container, layers, view,
        interactions: defaultInteractions({ mouseWheelZoom: false }).extend([new MouseWheelZoom({ duration: 120, timeout: 80, useAnchor: true, maxDelta: 1 })]),
      });
      map.set("overlayLayer", overlayLayer);
      map.updateSize();
      view.fit(extent, { size: map.getSize(), padding: [16, 16, 16, 16] });
      const initialResolution = view.getResolution() ?? 1;
      baseResolutionRef.current = initialResolution;
      minResolutionRef.current = initialResolution / 24;
      maxResolutionRef.current = initialResolution * 12;
      onScaleChangeRef.current?.(1);
      resolutionListenerRef.current = view.on("change:resolution", () => {
        const currentResolution = view.getResolution(); if (!currentResolution) return;
        const clampedResolution = clamp(currentResolution, minResolutionRef.current, maxResolutionRef.current);
        if (Math.abs(clampedResolution - currentResolution) > 1e-9) { view.setResolution(clampedResolution); return; }
        onScaleChangeRef.current?.(baseResolutionRef.current / clampedResolution);
      });
      resizeObserverRef.current = new ResizeObserver(() => { map.updateSize(); });
      resizeObserverRef.current.observe(container);
      mapRef.current = map; viewRef.current = view; vectorSourceRef.current = vectorSource; mapExtentRef.current = extent;
      rebuildFeaturesRef.current();
    };

    image.onload = initializeMap;
    image.onerror = () => { cleanup(); };
    image.src = imageUrl;
    if (image.complete && image.naturalWidth > 0) initializeMap();
    return () => { canceled = true; image.onload = null; image.onerror = null; cleanup(); };
  }, [imageUrl, overlayUrl]);

  useEffect(() => { rebuildFeatures(); }, [rebuildFeatures]);
  useEffect(() => { showLabelsRef.current = showLabels; vectorSourceRef.current?.changed(); }, [showLabels]);
  useEffect(() => { const map = mapRef.current; if (!map) return; const ol = map.get("overlayLayer"); if (ol) ol.setOpacity(overlayOpacity); }, [overlayOpacity]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
});
