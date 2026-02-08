# -*- coding: utf-8 -*-
"""
Configuración centralizada del pipeline ML de vineGAPdetect.

Pensada para ser portable:
- Usa rutas relativas al directorio `ml/` por defecto.
- Permite sobrescribir las rutas principales mediante variables de entorno.
"""

from os import getenv
from pathlib import Path

ML_ROOT = Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    raw = getenv(name)
    return Path(raw).expanduser() if raw else default


# === RUTAS DE DATOS ===
RASTER_DIR = _env_path("VINEGAP_RASTER_DIR", ML_ROOT / "data" / "raw" / "rasters")
VECTOR_DIR = _env_path("VINEGAP_VECTOR_DIR", ML_ROOT / "data" / "raw" / "vectors")

# Directorio de salida
OUTPUT_DIR = _env_path("VINEGAP_OUTPUT_DIR", ML_ROOT / "data" / "datasets" / "yolo_marras")


# === PARÁMETROS DE DATASET ===
PATCH_SIZE = 640
PATCH_OVERLAP = 0.5
MAX_WORKERS = 16

VALIDATION_SPLIT = 0.15
TEST_SPLIT = 0.15
RANDOM_SEED = 42


# === FILTRADO Y PROCESAMIENTO ===
# Si el dataset tiene una sola clase positiva anotada como cadena, ajusta aquí su nombre.
TARGET_CLASS = "True"

EDGE_BUFFER_PERCENTAGE = 2.0
MERGE_OVERLAPPING_BBOXES = True
BBOX_ENLARGEMENT_FACTOR = 0.25
SKIP_EMPTY_PATCHES = True


# === PARÁMETROS DE ENTRENAMIENTO ===
MODEL_BASE = "models/pretrained/yolo11n-obb.pt"
EPOCHS = 100
BATCH_SIZE = 16
IMAGE_SIZE = 640
TRAINING_NAME = "marras_detection"
PATIENCE = 25
