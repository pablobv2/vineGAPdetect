from __future__ import annotations

from typing import Any, Callable

import cv2
import numpy as np
from sahi.predict import get_sliced_prediction

from app.services.image_service import (
    encode_png_base64,
    extract_geotiff_patch_from_bytes,
    is_geotiff_filename,
    load_image_from_upload,
    resize_for_preview,
)
from app.services.model_registry import ModelRegistry


ProgressCallback = Callable[[int], None]


def _safe_layers(requested_layers: list[int], model) -> list[int]:
    max_idx = len(model.model.model) - 1
    return [idx for idx in requested_layers if 0 <= idx <= max_idx]


def _default_target_layers() -> list[int]:
    return [18]


def _extract_patch(
    payload: dict[str, Any],
    original: np.ndarray,
    x_off: int,
    y_off: int,
    imgsz: int,
) -> np.ndarray:
    if is_geotiff_filename(payload["filename"]):
        return extract_geotiff_patch_from_bytes(payload["file_bytes"], x_off, y_off, imgsz)

    patch = original[y_off : y_off + imgsz, x_off : x_off + imgsz].copy()
    if patch.shape[0] < imgsz or patch.shape[1] < imgsz:
        padded = np.zeros((imgsz, imgsz, 3), dtype=np.uint8)
        padded[: patch.shape[0], : patch.shape[1]] = patch
        patch = padded
    return patch


def _coerce_focus_bbox(payload: dict[str, Any]) -> list[float] | None:
    raw = payload.get("focus_bbox")
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(value) for value in raw]
    except (TypeError, ValueError):
        return None
    if not all(np.isfinite(value) for value in (x1, y1, x2, y2)):
        return None
    return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]


def _draw_focus_bbox(
    annotated_bgr: np.ndarray,
    focus_bbox: list[float],
    x_off: int,
    y_off: int,
    imgsz: int,
    confidence: float | None,
) -> bool:
    x1, y1, x2, y2 = focus_bbox
    px1 = int(round(np.clip(x1 - x_off, 0, imgsz - 1)))
    py1 = int(round(np.clip(y1 - y_off, 0, imgsz - 1)))
    px2 = int(round(np.clip(x2 - x_off, 0, imgsz - 1)))
    py2 = int(round(np.clip(y2 - y_off, 0, imgsz - 1)))
    if px2 <= px1 or py2 <= py1:
        return False

    color_bgr = (0, 200, 255)
    cv2.rectangle(annotated_bgr, (px1, py1), (px2, py2), color_bgr, 2)
    label = "hist"
    if confidence is not None and np.isfinite(confidence):
        label = f"hist {confidence:.2f}"
    (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    label_y = max(label_h + 4, py1 - 10)
    cv2.rectangle(
        annotated_bgr,
        (px1, label_y - label_h - 4),
        (px1 + label_w + 6, label_y + 3),
        color_bgr,
        -1,
    )
    cv2.putText(
        annotated_bgr,
        label,
        (px1 + 3, label_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
    )
    return True


def _pad_to_stride(image_rgb: np.ndarray, stride: int = 32) -> tuple[np.ndarray, int, int]:
    height, width = image_rgb.shape[:2]
    padded_width = int(np.ceil(width / stride) * stride)
    padded_height = int(np.ceil(height / stride) * stride)
    pad_right = max(0, padded_width - width)
    pad_bottom = max(0, padded_height - height)
    if pad_right == 0 and pad_bottom == 0:
        return image_rgb, width, height
    padded = cv2.copyMakeBorder(
        image_rgb,
        0,
        pad_bottom,
        0,
        pad_right,
        cv2.BORDER_REPLICATE,
    )
    return padded, width, height


class XAIService:
    def __init__(self, model_registry: ModelRegistry) -> None:
        self.model_registry = model_registry

    def run(self, payload: dict[str, Any], progress: ProgressCallback) -> dict[str, Any]:
        progress(5)
        loaded = load_image_from_upload(payload["file_bytes"], payload["filename"])
        original = loaded.image_rgb
        h_orig, w_orig = original.shape[:2]
        imgsz = int(payload["imgsz"])
        requested_conf = float(payload["conf_threshold"])
        if str(payload.get("xai_scope", "patch")).strip().lower() == "full":
            return self._run_full_parcel(payload, original, requested_conf, progress)
        focus_bbox = _coerce_focus_bbox(payload)
        focus_confidence = payload.get("focus_confidence")
        if focus_confidence is not None:
            try:
                focus_confidence = float(focus_confidence)
            except (TypeError, ValueError):
                focus_confidence = None
        progress(15)

        req_cx = payload.get("cx")
        req_cy = payload.get("cy")
        if req_cx is not None and req_cy is not None:
            cx, cy = int(req_cx), int(req_cy)
            progress(35)
        elif focus_bbox is not None:
            cx = int(round((focus_bbox[0] + focus_bbox[2]) / 2))
            cy = int(round((focus_bbox[1] + focus_bbox[3]) / 2))
            progress(35)
        else:
            sahi_model = self.model_registry.get_sahi_model()
            sahi_model.confidence_threshold = min(requested_conf, 0.99)
            result = get_sliced_prediction(
                image=original,
                detection_model=sahi_model,
                slice_height=imgsz,
                slice_width=imgsz,
                overlap_height_ratio=0.2,
                overlap_width_ratio=0.2,
                verbose=0,
            )
            best_det = None
            best_conf = -1.0
            for pred in result.object_prediction_list:
                conf = float(pred.score.value)
                if conf > best_conf:
                    best_conf = conf
                    best_det = pred
            if best_det:
                bbox = [int(round(value)) for value in best_det.bbox.to_xyxy()]
                cx = (bbox[0] + bbox[2]) // 2
                cy = (bbox[1] + bbox[3]) // 2
            else:
                cx, cy = w_orig // 2, h_orig // 2
            progress(35)

        x_off = int(max(0, cx - imgsz // 2))
        y_off = int(max(0, cy - imgsz // 2))
        if x_off + imgsz > w_orig:
            x_off = max(0, w_orig - imgsz)
        if y_off + imgsz > h_orig:
            y_off = max(0, h_orig - imgsz)

        patch = _extract_patch(payload, original, x_off, y_off, imgsz)
        img_bgr = cv2.cvtColor(patch, cv2.COLOR_RGB2BGR)
        img_for_viz = np.float32(patch) / 255.0
        progress(50)

        yolo = self.model_registry.get_yolo_model()
        results = yolo(img_bgr, verbose=False, conf=requested_conf)
        detections = results[0]
        has_detections = (
            getattr(detections, "obb", None) is not None and len(detections.obb) > 0
        ) or (
            getattr(detections, "boxes", None) is not None and len(detections.boxes) > 0
        )

        annotated_bgr = cv2.cvtColor(patch, cv2.COLOR_RGB2BGR)
        box_color_bgr = (255, 0, 255)
        layers = _safe_layers(payload["target_layers"], yolo) or _default_target_layers()

        if not has_detections and focus_bbox is None:
            cam_placeholder_bgr = annotated_bgr.copy()
            cv2.putText(
                annotated_bgr,
                "SIN DETECCIONES",
                (20, imgsz // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                2,
            )
            cv2.putText(
                cam_placeholder_bgr,
                "N/A",
                (imgsz // 2 - 40, imgsz // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (255, 255, 0),
                2,
            )
            annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
            cam_overlay = cv2.cvtColor(cam_placeholder_bgr, cv2.COLOR_BGR2RGB)
            combined = np.hstack((patch, annotated_rgb, cam_overlay))
            progress(100)
            return {
                "requested_method": "eigencam",
                "method": "eigencam",
                "width": int(combined.shape[1]),
                "height": int(combined.shape[0]),
                "overlay_png_base64": encode_png_base64(cam_overlay),
                "combined_png_base64": encode_png_base64(combined),
                "used_conf_threshold": requested_conf,
                "used_target_layers": layers,
                "has_detections": False,
                "fallback_reason": None,
                "fallback_details": None,
            }

        if getattr(detections, "obb", None) is not None and len(detections.obb) > 0:
            for det in detections.obb:
                points = det.xyxyxyxy.cpu().numpy().astype(int).reshape(-1, 2)
                conf = float(det.conf.item())
                cv2.polylines(annotated_bgr, [points], isClosed=True, color=box_color_bgr, thickness=2)
                label = f"{conf:.2f}"
                (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                label_pos = (int(points[0][0]), int(points[0][1]) - 10)
                cv2.rectangle(
                    annotated_bgr,
                    (label_pos[0], label_pos[1] - label_h),
                    (label_pos[0] + label_w, label_pos[1] + 3),
                    box_color_bgr,
                    -1,
                )
                cv2.putText(
                    annotated_bgr,
                    label,
                    label_pos,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                )
        elif getattr(detections, "boxes", None) is not None and len(detections.boxes) > 0:
            for det in detections.boxes:
                x1, y1, x2, y2 = map(int, det.xyxy[0].cpu().numpy())
                conf = float(det.conf.item())
                cv2.rectangle(annotated_bgr, (x1, y1), (x2, y2), box_color_bgr, 2)
                label = f"{conf:.2f}"
                (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                label_pos = (x1, y1 - 10)
                cv2.rectangle(
                    annotated_bgr,
                    (label_pos[0], label_pos[1] - label_h),
                    (label_pos[0] + label_w, label_pos[1] + 3),
                    box_color_bgr,
                    -1,
                )
                cv2.putText(
                    annotated_bgr,
                    label,
                    label_pos,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                )
        elif focus_bbox is not None:
            _draw_focus_bbox(annotated_bgr, focus_bbox, x_off, y_off, imgsz, focus_confidence)
        progress(70)

        cam_modules = self.model_registry.get_cam_modules()
        target_layers_modules = [yolo.model.model[idx] for idx in layers]

        try:
            cam = cam_modules["eigencam"](yolo, target_layers_modules, task="od")
            grayscale_cam = cam(img_bgr)[0, :, :]
            cam_overlay = cam_modules["show_cam_on_image"](img_for_viz, grayscale_cam, use_rgb=True)
        except Exception as exc:
            if focus_bbox is not None and not has_detections:
                annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
                combined = np.hstack((patch, annotated_rgb, annotated_rgb))
                progress(100)
                return {
                    "requested_method": "eigencam",
                    "method": "eigencam",
                    "width": int(combined.shape[1]),
                    "height": int(combined.shape[0]),
                    "overlay_png_base64": encode_png_base64(annotated_rgb),
                    "combined_png_base64": encode_png_base64(combined),
                    "used_conf_threshold": requested_conf,
                    "used_target_layers": layers,
                    "has_detections": False,
                    "fallback_reason": "stored_focus_bbox_no_cam",
                    "fallback_details": f"No se pudo redetectar el parche con el umbral indicado ni generar CAM; se muestra la deteccion historica seleccionada. Detalle: {exc}",
                }
            raise RuntimeError(f"Error durante la generacion de CAM: {exc}") from exc
        progress(90)

        annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
        combined = np.hstack((patch, annotated_rgb, cam_overlay))
        progress(100)

        return {
            "requested_method": "eigencam",
            "method": "eigencam",
            "width": int(combined.shape[1]),
            "height": int(combined.shape[0]),
            "overlay_png_base64": encode_png_base64(cam_overlay),
            "combined_png_base64": encode_png_base64(combined),
            "used_conf_threshold": requested_conf,
            "used_target_layers": layers,
            "has_detections": has_detections,
            "fallback_reason": None if has_detections else "stored_focus_bbox",
            "fallback_details": None
            if has_detections
            else "No se redetecto el parche con el umbral indicado; se muestra la deteccion historica seleccionada.",
        }

    def _run_full_parcel(
        self,
        payload: dict[str, Any],
        original: np.ndarray,
        requested_conf: float,
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        progress(20)
        max_side = int(payload.get("full_max_side") or 1280)
        full_rgb = resize_for_preview(original, max_side=max(320, min(max_side, 1920)))
        padded_rgb, valid_width, valid_height = _pad_to_stride(full_rgb, stride=32)
        img_bgr = cv2.cvtColor(padded_rgb, cv2.COLOR_RGB2BGR)
        img_for_viz = np.float32(padded_rgb) / 255.0
        progress(45)

        yolo = self.model_registry.get_yolo_model()
        layers = _safe_layers(payload["target_layers"], yolo) or _default_target_layers()
        _ = yolo(img_bgr, verbose=False, conf=requested_conf)
        progress(60)

        cam_modules = self.model_registry.get_cam_modules()
        target_layers_modules = [yolo.model.model[idx] for idx in layers]
        try:
            cam = cam_modules["eigencam"](yolo, target_layers_modules, task="od")
            grayscale_cam = cam(img_bgr)[0, :, :]
            grayscale_cam = grayscale_cam[:valid_height, :valid_width]
            img_for_viz_cropped = np.float32(full_rgb) / 255.0
            heat = np.uint8(255 * np.clip(grayscale_cam, 0.0, 1.0))
            heat_bgr = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
            heat_rgb = cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)
            combined = cam_modules["show_cam_on_image"](img_for_viz_cropped, grayscale_cam, use_rgb=True)
        except Exception as exc:
            raise RuntimeError(f"Error durante la generacion de CAM de parcela completa: {exc}") from exc
        progress(100)

        return {
            "requested_method": "eigencam",
            "method": "eigencam",
            "xai_scope": "full",
            "width": int(full_rgb.shape[1]),
            "height": int(full_rgb.shape[0]),
            "overlay_png_base64": encode_png_base64(heat_rgb),
            "combined_png_base64": encode_png_base64(combined),
            "used_conf_threshold": requested_conf,
            "used_target_layers": layers,
            "has_detections": None,
            "fallback_reason": None,
            "fallback_details": None,
        }
