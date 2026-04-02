# -*- coding: utf-8 -*-
"""
Script de Explicabilidad (XAI) para Modelos YOLOv11-OBB - vineGAPdetect.

Genera visualizaciones offline con Eigen-CAM o Grad-CAM sobre imágenes de entrada
para documentar el comportamiento del modelo fuera de la app web.
"""
import sys
import argparse
import logging
from pathlib import Path
from typing import List

import cv2
import torch
import numpy as np
from PIL import Image
from tqdm import tqdm
from ultralytics import YOLO

# --- Importar los módulos clave de yolo-cam ---
try:
    from yolo_cam.eigen_cam import EigenCAM
    from yolo_cam.grad_cam import GradCAM
    from yolo_cam.utils.image import show_cam_on_image
    from yolo_cam.utils.model_targets import YOLOBoxScoreTarget
except ImportError:
    print("\n" + "="*80)
    print("Error: No se pudo importar el módulo 'yolo_cam'.")
    print("Por favor, sigue las instrucciones del README para colocar la carpeta 'yolo_cam' en tu proyecto.")
    print("="*80 + "\n")
    sys.exit(1)

# --- Configuración del Logger ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)


def _default_layers_for_method(method: str) -> List[int]:
    return [16] if method == "gradcam" else [16, 19, 22]


def _build_gradcam_targets(detections, model) -> list[YOLOBoxScoreTarget] | None:
    candidates = []
    if getattr(detections, "obb", None) is not None and len(detections.obb) > 0:
        candidates.extend(list(detections.obb))
    elif getattr(detections, "boxes", None) is not None and len(detections.boxes) > 0:
        candidates.extend(list(detections.boxes))

    if not candidates:
        return None

    target_det = max(candidates, key=lambda det: float(det.conf.item()))
    if hasattr(target_det, "xyxyxyxy"):
        target_xy = tuple(np.mean(target_det.xyxyxyxy.cpu().numpy().reshape(-1, 2), axis=0).tolist())
    else:
        x1, y1, x2, y2 = target_det.xyxy[0].cpu().numpy().tolist()
        target_xy = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    target_category = int(target_det.cls[0].item()) if hasattr(target_det, "cls") else None
    num_extra_channels = int(getattr(model.model.model[-1], "ne", 0) or 0)
    return [
        YOLOBoxScoreTarget(
            category=target_category,
            num_extra_channels=num_extra_channels,
            target_xy=target_xy,
        )
    ]

def print_banner():
    """Imprime un banner de bienvenida para el script."""
    banner = """
    ╔════════════════════════════════════════════════════════════╗
    ║      vineGAPdetect - Módulo de Explicabilidad (XAI) con CAM      ║
    ║                  Visualizando Decisiones de YOLO             ║
    ╚════════════════════════════════════════════════════════════╝
    """
    print(banner)

def find_latest_model(project_dir: Path) -> Path:
    """Encuentra el archivo 'best.pt' del entrenamiento más reciente."""
    experiments = [d for d in project_dir.iterdir() if d.is_dir()]
    if not experiments:
        raise FileNotFoundError(f"No se encontraron directorios de experimentos en {project_dir}")
    latest_experiment = max(experiments, key=lambda d: d.stat().st_mtime)
    best_model_path = latest_experiment / "weights" / "best.pt"
    if not best_model_path.exists():
        raise FileNotFoundError(f"No se encontró 'best.pt' en el experimento más reciente: {latest_experiment}")
    logger.info(f"Modelo más reciente encontrado: {best_model_path}")
    return best_model_path

def generate_explanation(
    model: YOLO,
    image_path: Path,
    output_path: Path,
    method: str,
    target_layers: List[int],
    conf_threshold: float,
    img_size: int = 640,
):
    """
    Genera y guarda una imagen de explicabilidad, mostrando solo confianza en los labels.
    """
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            logger.warning(f"No se pudo leer la imagen: {image_path}. Omitiendo.")
            return

        img_resized = cv2.resize(img, (img_size, img_size))
        original_img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_for_viz = np.float32(original_img_rgb) / 255.0

        results = model(img_resized, verbose=False, conf=conf_threshold)

        detections = None
        if hasattr(results[0], 'obb') and results[0].obb is not None: detections = results[0].obb
        elif hasattr(results[0], 'boxes') and results[0].boxes is not None: detections = results[0].boxes

        if detections is None or len(detections) == 0:
            logger.warning(f"No se detectaron objetos en {image_path.name} con conf > {conf_threshold}.")
            annotated_img = original_img_rgb.copy()
            cam_placeholder = original_img_rgb.copy()
            cv2.putText(annotated_img, "SIN DETECCIONES", (50, img_size // 2), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3, cv2.LINE_AA)
            cv2.putText(cam_placeholder, "N/A", (img_size // 2 - 50, img_size // 2), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 0), 3, cv2.LINE_AA)
            combined_image = np.hstack((original_img_rgb, annotated_img, cam_placeholder))
            Image.fromarray(combined_image).save(output_path)
            return

        annotated_img = cv2.resize(results[0].plot(labels=False, conf=True), (img_size, img_size))
        
        target_layers_modules = [model.model.model[i] for i in target_layers]
        targets = None
        if method == "gradcam":
            cam = GradCAM(model, target_layers_modules, task='od')
            targets = _build_gradcam_targets(results[0], model)
        else:
            cam = EigenCAM(model, target_layers_modules, task='od')
        
        grayscale_cam = cam(img_resized, targets=targets)[0, :, :]
        
        cam_image = show_cam_on_image(img_for_viz, grayscale_cam, use_rgb=True)
        
        annotated_img_rgb = cv2.cvtColor(annotated_img, cv2.COLOR_BGR2RGB)
        
        combined_image = np.hstack((original_img_rgb, annotated_img_rgb, cam_image))
        Image.fromarray(combined_image).save(output_path)

    except Exception as e:
        logger.error(f"Error procesando la imagen {image_path.name}: {e}")
        logger.exception("Detalles del error:")

def main():
    # El resto del script (función main) no necesita cambios.
    print_banner()
    parser = argparse.ArgumentParser(description="Genera visualizaciones de explicabilidad (Eigen-CAM o Grad-CAM) para modelos YOLO.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--model", type=str, default=None, help="Ruta al modelo .pt entrenado. Si no, busca el último en ./results.")
    parser.add_argument("--image", type=str, required=True, help="Ruta a una imagen o directorio con imágenes.")
    parser.add_argument("--output-dir", type=str, default="./results/Explainability", help="Directorio de salida.")
    parser.add_argument("--method", choices=["eigencam", "gradcam"], default="eigencam", help="Método XAI a utilizar.")
    parser.add_argument("--target-layers", nargs='+', type=int, default=None, help="Índices de capas a analizar (e.g., 16 19 22). Si no se indican, se usan valores por defecto según el método.")
    parser.add_argument("--conf-threshold", type=float, default=0.25, help="Umbral de confianza para las detecciones.")
    parser.add_argument("--imgsz", type=int, default=640, help="Tamaño de imagen para el procesamiento.")
    parser.add_argument("--device", type=str, default="", help="Dispositivo a usar ('cpu', 'cuda:0'). Auto-detecta por defecto.")
    args = parser.parse_args()

    model_path = Path(args.model) if args.model else find_latest_model(Path("./results/vineGAPdetect_Training"))
    if not model_path.exists():
        logger.error(f"El archivo del modelo no existe: {model_path}"); sys.exit(1)
        
    image_source = Path(args.image)
    if not image_source.exists():
        logger.error(f"La ruta de la imagen o directorio no existe: {image_source}"); sys.exit(1)

    output_dir = Path(args.output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Las salidas se guardarán en: {output_dir}")

    logger.info(f"Cargando modelo desde: {model_path}")
    device = args.device if args.device else ('cuda' if torch.cuda.is_available() else 'cpu')
    try:
        model = YOLO(model_path); model.to(device)
        logger.info(f"Modelo cargado exitosamente en el dispositivo: '{device}'")
    except Exception as e:
        logger.error(f"No se pudo cargar el modelo: {e}"); sys.exit(1)

    if image_source.is_dir():
        patterns = ["*.[pP][nN][gG]", "*.[jJ][pP][gG]", "*.[jJ][pP][eE][gG]", "*.[tT][iI][fF]", "*.[tT][iI][fF][fF]"]
        image_files = []
        for pattern in patterns:
            image_files.extend(image_source.glob(pattern))
    else:
        image_files = [image_source]
    if not image_files:
        logger.error("No se encontraron imágenes .png o .jpg para procesar."); sys.exit(1)
        
    target_layers = args.target_layers or _default_layers_for_method(args.method)
    logger.info(f"Se procesarán {len(image_files)} imagen(es)...")
    logger.info(f"Método XAI: {args.method}")
    logger.info(f"Usando capas objetivo con índices: {target_layers}")

    for img_path in tqdm(image_files, desc="Generando Explicaciones"):
        output_filename = f"{img_path.stem}_explanation.png"
        generate_explanation(
            model,
            img_path,
            output_dir / output_filename,
            args.method,
            target_layers,
            args.conf_threshold,
            args.imgsz,
        )

    logger.info("\n" + "="*60 + "\n✓ Proceso de explicabilidad completado.\n" + f"Resultados guardados en: {output_dir.resolve()}\n" + "="*60)

if __name__ == "__main__":
    main()
