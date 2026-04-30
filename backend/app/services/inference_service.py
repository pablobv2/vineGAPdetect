from __future__ import annotations

import json
import logging
import re
import hashlib
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

import numpy as np
from sahi.predict import get_sliced_prediction
from shapely.geometry import Polygon as ShapelyPolygon
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import AnalysisHistory
from app.services.image_service import load_image_from_upload
from app.services.model_registry import ModelRegistry


ProgressCallback = Callable[[int], None]
logger = logging.getLogger(__name__)


def _obb_nms(predictions: list, ios_threshold: float = 0.3) -> list:
    """NMS usando el polígono OBB real (shapely IOS). Evita duplicados entre slices
    incluso cuando los bbox axis-aligned tienen bajo solapamiento por la rotación."""
    if len(predictions) <= 1:
        return predictions

    def _poly(pred) -> ShapelyPolygon:
        mask = getattr(pred, "mask", None)
        if mask and getattr(mask, "segmentation", None) and mask.segmentation:
            seg = mask.segmentation[0]
            if len(seg) >= 8:
                pts = [(seg[i], seg[i + 1]) for i in range(0, len(seg), 2)]
                try:
                    p = ShapelyPolygon(pts)
                    if p.is_valid and p.area > 0:
                        return p
                except Exception:
                    pass
        x1, y1, x2, y2 = pred.bbox.to_xyxy()
        return ShapelyPolygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

    polys = [_poly(p) for p in predictions]
    order = sorted(range(len(predictions)), key=lambda i: float(predictions[i].score.value), reverse=True)

    suppressed: set[int] = set()
    keep: list = []
    for pos, i in enumerate(order):
        if i in suppressed:
            continue
        keep.append(predictions[i])
        poly_i = polys[i]
        area_i = poly_i.area
        for j in order[pos + 1:]:
            if j in suppressed:
                continue
            try:
                inter = poly_i.intersection(polys[j]).area
                smaller = min(area_i, polys[j].area)
                if smaller > 0 and inter / smaller >= ios_threshold:
                    suppressed.add(j)
            except Exception:
                pass

    return keep


def _persist_source_artifact(content: bytes, filename: str) -> str | None:
    if not content:
        return None
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "upload.bin"
    suffix = "".join(settings.history_artifact_dir.joinpath(safe_name).suffixes)[-16:]
    artifact_path = settings.history_artifact_dir / f"{datetime.utcnow():%Y%m%d%H%M%S}_{uuid4().hex}{suffix}"
    artifact_path.write_bytes(content)
    try:
        return artifact_path.relative_to(settings.repo_root).as_posix()
    except ValueError:
        return str(artifact_path)


def _longest_polygon_side_m(polygon: list[list[float]], resolution_x: float, resolution_y: float) -> float | None:
    if len(polygon) < 2:
        return None

    points: list[tuple[float, float]] = []
    for point in polygon:
        if not isinstance(point, list) or len(point) < 2:
            return None
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            return None
        if not np.isfinite(x) or not np.isfinite(y):
            return None
        points.append((x, y))

    if len(points) >= 2 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 2:
        return None

    scale_x = abs(float(resolution_x))
    scale_y = abs(float(resolution_y))
    side_lengths: list[float] = []
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        dx_m = (x2 - x1) * scale_x
        dy_m = (y2 - y1) * scale_y
        length = float(np.hypot(dx_m, dy_m))
        if np.isfinite(length):
            side_lengths.append(length)

    return max(side_lengths) if side_lengths else None


def calculate_missing_vines(
    bbox: list[int],
    resolution_x: float,
    resolution_y: float,
    typical_vine_width: float,
    obb_polygon: list[list[float]] | None = None,
) -> int:
    if obb_polygon:
        oriented_length = _longest_polygon_side_m(obb_polygon, resolution_x, resolution_y)
        if oriented_length is not None:
            return max(1, round(oriented_length / typical_vine_width))

    x1, y1, x2, y2 = bbox
    width_px, height_px = abs(x2 - x1), abs(y2 - y1)
    width_m = width_px * abs(resolution_x)
    height_m = height_px * abs(resolution_y)
    gap_length = max(width_m, height_m)
    return max(1, round(gap_length / typical_vine_width))


def _summarize_detections(detections: list[dict[str, Any]]) -> dict[str, Any]:
    confidence_mean = float(np.mean([d["confidence"] for d in detections])) if detections else 0.0
    estimated_total = int(sum(d["estimated_missing_vines"] for d in detections))
    return {
        "detections_count": len(detections),
        "confidence_mean": round(confidence_mean, 6),
        "estimated_missing_vines_total": estimated_total,
    }


class InferenceService:
    def __init__(
        self,
        model_registry: ModelRegistry,
        session_factory: sessionmaker | None = None,
    ) -> None:
        self.model_registry = model_registry
        self._sf = session_factory

    def run(self, payload: dict[str, Any], progress: ProgressCallback) -> dict[str, Any]:
        start = datetime.now()
        progress(5)

        loaded = load_image_from_upload(payload["file_bytes"], payload["filename"])
        image = loaded.image_rgb
        height, width = image.shape[:2]
        progress(20)

        sahi_model = self.model_registry.get_sahi_model()
        sahi_model.confidence_threshold = min(float(payload["confidence_threshold"]), 0.99)

        sahi_result = get_sliced_prediction(
            image=image,
            detection_model=sahi_model,
            slice_height=int(payload["slice_size"]),
            slice_width=int(payload["slice_size"]),
            overlap_height_ratio=float(payload["overlap_ratio"]),
            overlap_width_ratio=float(payload["overlap_ratio"]),
            postprocess_type="GREEDYNMM",
            postprocess_match_metric="IOS",
            verbose=0,
        )
        progress(70)

        detections: list[dict[str, Any]] = []
        conf_threshold = float(payload["confidence_threshold"])
        vine_width = float(payload["typical_vine_width"])

        predictions = _obb_nms(sahi_result.object_prediction_list)
        for pred in predictions:
            confidence = float(pred.score.value)
            if confidence < conf_threshold:
                continue

            bbox_xyxy = [int(round(value)) for value in pred.bbox.to_xyxy()]
            polygon: list[list[float]] | None = None

            mask = getattr(pred, "mask", None)
            if mask and getattr(mask, "segmentation", None) and mask.segmentation:
                segment = mask.segmentation[0]
                if len(segment) >= 8:
                    polygon = []
                    for i in range(0, len(segment), 2):
                        polygon.append([float(segment[i]), float(segment[i + 1])])

            if polygon is None:
                x1, y1, x2, y2 = bbox_xyxy
                polygon = [
                    [float(x1), float(y1)],
                    [float(x2), float(y1)],
                    [float(x2), float(y2)],
                    [float(x1), float(y2)],
                ]

            estimated_count = calculate_missing_vines(
                bbox_xyxy,
                loaded.resolution_x,
                loaded.resolution_y,
                vine_width,
                polygon,
            )

            detections.append(
                {
                    "id": len(detections) + 1,
                    "class_name": str(pred.category.name),
                    "confidence": round(confidence, 6),
                    "bbox_xyxy": bbox_xyxy,
                    "obb_polygon": polygon,
                    "estimated_missing_vines": estimated_count,
                }
            )

        elapsed = (datetime.now() - start).total_seconds()
        progress(90)

        display_threshold = float(payload.get("display_confidence_threshold", 0.55))
        history_dets = [d for d in detections if d["confidence"] >= display_threshold]
        summary_all = _summarize_detections(detections)
        summary_display = _summarize_detections(history_dets)

        result = {
            "image_meta": {
                "width": int(width),
                "height": int(height),
                "file_type": loaded.file_type,
                "resolution_x": float(loaded.resolution_x),
                "resolution_y": float(loaded.resolution_y),
                "resolution_unit": loaded.resolution_unit,
                "crs": loaded.crs,
                "transform": loaded.transform,
                "parcel_area_hectares": loaded.parcel_area_hectares,
                "location_center_lat": loaded.location_center_lat,
                "location_center_lon": loaded.location_center_lon,
                "acquisition_date": loaded.acquisition_date,
            },
            "parameters": {
                "capture_confidence_threshold": conf_threshold,
                "display_confidence_threshold": display_threshold,
                "typical_vine_width": vine_width,
                "slice_size": int(payload["slice_size"]),
                "overlap_ratio": float(payload["overlap_ratio"]),
                "model_path": str(self.model_registry.model_path),
            },
            "summary": {
                **summary_display,
                "processing_time_seconds": round(elapsed, 3),
            },
            "summary_all": {
                **summary_all,
                "processing_time_seconds": round(elapsed, 3),
            },
            "summary_display": {
                **summary_display,
                "processing_time_seconds": round(elapsed, 3),
            },
            "detections": detections,
        }

        progress(100)

        if self._sf is not None:
            try:
                from app.db.database import cleanup_old_unsaved
                with self._sf() as _db:
                    _engine = _db.get_bind()
                cleanup_old_unsaved(_engine)
            except Exception as exc:
                logger.warning("Draft cleanup failed (non-fatal): %s", exc)

            try:
                source_artifact_path = _persist_source_artifact(payload["file_bytes"], payload["filename"])
                user_id = payload.get("user_id")
                filename = payload["filename"]
                file_size_bytes = len(payload["file_bytes"])
                source_sha256 = hashlib.sha256(payload["file_bytes"]).hexdigest()
                history_row = AnalysisHistory(
                    user_id=user_id,
                    filename=filename,
                    original_filename=filename,
                    executed_at=datetime.utcnow(),
                    detection_count=summary_display["detections_count"],
                    all_detection_count=summary_all["detections_count"],
                    mean_confidence=summary_display["confidence_mean"] if history_dets else None,
                    estimated_missing=summary_display["estimated_missing_vines_total"],
                    processing_time_s=round(elapsed, 3),
                    capture_confidence_threshold=conf_threshold,
                    display_confidence_threshold=display_threshold,
                    typical_vine_width=vine_width,
                    slice_size=int(payload["slice_size"]),
                    overlap_ratio=float(payload["overlap_ratio"]),
                    model_path=str(self.model_registry.model_path),
                    source_width=int(width),
                    source_height=int(height),
                    file_type=loaded.file_type,
                    resolution_x=float(loaded.resolution_x),
                    resolution_y=float(loaded.resolution_y),
                    resolution_unit=loaded.resolution_unit,
                    crs=loaded.crs,
                    transform_json=json.dumps(loaded.transform) if loaded.transform else None,
                    parcel_area_hectares=loaded.parcel_area_hectares,
                    location_center_lat=loaded.location_center_lat,
                    location_center_lon=loaded.location_center_lon,
                    acquisition_date=loaded.acquisition_date,
                    source_artifact_path=source_artifact_path,
                    source_file_size_bytes=file_size_bytes,
                    source_sha256=source_sha256,
                    result_json=json.dumps(result),
                    saved=False,
                )
                with self._sf() as db:
                    db.add(history_row)
                    db.commit()
                    db.refresh(history_row)
                result["history_id"] = history_row.id
            except Exception as exc:
                logger.exception("Could not persist analysis history: %s", exc)

        return result
