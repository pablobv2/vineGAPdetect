from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import torch
from sahi import AutoDetectionModel
from ultralytics import YOLO

from app.core.config import Settings, settings


class ModelRegistry:
    """Carga y reutiliza modelos YOLO, adaptador SAHI y modulos CAM segun la configuracion.

    La carga es perezosa para evitar inicializar modelos pesados hasta que una
    ruta los necesita. Expone un modelo Ultralytics directo para XAI, un modelo
    SAHI para inferencia por teselas y comprueba si la libreria local yolo_cam
    esta disponible para generar mapas Eigen-CAM.
    """
    def __init__(self, cfg: Settings = settings) -> None:
        self.cfg = cfg
        self._yolo_model: YOLO | None = None
        self._sahi_model: AutoDetectionModel | None = None
        self._cam_modules: dict[str, Any] | None = None

    @property
    def device(self) -> str:
        if self.cfg.device:
            return self.cfg.device
        return "cuda:0" if torch.cuda.is_available() else "cpu"

    @property
    def model_path(self) -> Path:
        return self.cfg.model_path

    def is_model_available(self) -> bool:
        return self.model_path.exists()

    def get_yolo_model(self) -> YOLO:
        if self._yolo_model is None:
            self._yolo_model = YOLO(str(self.model_path))
            self._yolo_model.to(self.device)
        return self._yolo_model

    def get_sahi_model(self) -> AutoDetectionModel:
        if self._sahi_model is None:
            self._sahi_model = AutoDetectionModel.from_pretrained(
                model_type="yolov8",
                model_path=str(self.model_path),
                confidence_threshold=0.05,
                device=self.device,
            )
        return self._sahi_model

    def _ensure_cam_path(self) -> None:
        yolo_cam_path = str(self.cfg.yolo_cam_path)
        if yolo_cam_path not in sys.path:
            sys.path.insert(0, yolo_cam_path)

    def get_cam_modules(self) -> dict[str, Any]:
        if self._cam_modules is not None:
            return self._cam_modules

        self._ensure_cam_path()
        from yolo_cam.eigen_cam import EigenCAM  # type: ignore
        from yolo_cam.utils.image import show_cam_on_image  # type: ignore

        self._cam_modules = {
            "eigencam": EigenCAM,
            "show_cam_on_image": show_cam_on_image,
        }
        return self._cam_modules

    @property
    def yolo_cam_available(self) -> bool:
        try:
            self.get_cam_modules()
            return True
        except Exception:
            return False
