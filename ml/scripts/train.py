# -*- coding: utf-8 -*-
"""
Script de Entrenamiento para Modelos YOLOv11-OBB - vineGAPdetect
Detección de Marras con Oriented Bounding Boxes

Uso básico:
    python scripts/train.py --dataset-dir ./data/datasets/yolo_marras

Uso avanzado:
    python scripts/train.py \
        --dataset-dir ./data/datasets/yolo_marras \
        --model models/pretrained/yolo11l-obb.pt \
        --epochs 100 \
        --batch 16 \
        --name experimento_v1
"""
import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple

import torch
from ultralytics import YOLO

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
TRAINING_RESULTS_DIR = RESULTS_DIR / "vineGAPdetect_Training"


def print_banner():
    """Imprime banner de inicio del script."""
    print("vineGAPdetect - entrenamiento YOLOv11-OBB")


def check_environment() -> Dict[str, str]:
    """Verifica el entorno de ejecución y recursos disponibles."""
    env_info = {
        "Python": sys.version.split()[0],
        "PyTorch": torch.__version__,
        "CUDA disponible": "Sí" if torch.cuda.is_available() else "No",
    }

    if torch.cuda.is_available():
        env_info["GPU"] = torch.cuda.get_device_name(0)
        env_info["CUDA version"] = torch.version.cuda
        env_info["GPUs disponibles"] = str(torch.cuda.device_count())
    else:
        env_info["Dispositivo"] = "CPU (Advertencia: entrenamiento será muy lento)"

    logger.info("=== Entorno de Ejecución ===")
    for key, value in env_info.items():
        logger.info(f"  {key}: {value}")

    return env_info


def validate_dataset(dataset_dir: Path) -> Tuple[bool, str]:
    """Valida que el dataset tenga la estructura correcta."""
    required_dirs = [
        dataset_dir / "images" / "train",
        dataset_dir / "images" / "validation",
        dataset_dir / "labels" / "train",
        dataset_dir / "labels" / "validation",
    ]

    for dir_path in required_dirs:
        if not dir_path.exists():
            return False, f"Falta directorio requerido: {dir_path}"

    # Verificar que hay imágenes
    train_images = list((dataset_dir / "images" / "train").glob("*.png"))
    if len(train_images) == 0:
        return False, "No se encontraron imágenes de entrenamiento (.png)"

    return True, f"Dataset válido: {len(train_images)} imágenes de entrenamiento"


def get_dataset_stats(dataset_dir: Path) -> Dict[str, int]:
    """Obtiene estadísticas del dataset."""
    stats = {}
    for split in ["train", "validation", "test"]:
        img_dir = dataset_dir / "images" / split
        lbl_dir = dataset_dir / "labels" / split

        if img_dir.exists():
            stats[f"{split}_images"] = len(list(img_dir.glob("*.png")))
            stats[f"{split}_labels"] = len(list(lbl_dir.glob("*.txt"))) if lbl_dir.exists() else 0

    return stats


def get_class_map(dataset_dir: Path) -> dict:
    """Lee el mapa de clases desde el reporte del patcher."""
    report_path = dataset_dir / 'patcher_report.json'

    if not report_path.exists():
        raise FileNotFoundError(
            f"No se encontró {report_path}\n"
            "Falta ejecutar previamente 'python scripts/generar_parches.py'."
        )

    with open(report_path, 'r') as f:
        data = json.load(f)

    if 'class_map' not in data:
        raise KeyError(
            "El reporte no contiene 'class_map'.\n"
            "Regenera el dataset con la versión actualizada de generar_parches.py"
        )

    return {k: int(v) for k, v in data['class_map'].items()}


def create_yaml(dataset_dir: Path, class_map: dict) -> Path:
    """Crea el archivo YAML de configuración para YOLO."""
    yaml_content = f"""path: {dataset_dir.resolve()}
train: images/train
val: images/validation
test: images/test

names:
{os.linesep.join([f'  {i}: {n}' for n, i in sorted(class_map.items(), key=lambda x: x[1])])}
"""
    yaml_path = dataset_dir / "dataset.yaml"
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)

    logger.info(f"Archivo YAML generado: {yaml_path}")
    return yaml_path


def get_unique_experiment_name(base_name: str, project_dir: Path) -> str:
    """
    Genera un nombre único para el experimento.
    Si el nombre existe, añade sufijo _v2, _v3, etc.
    """
    experiment_dir = project_dir / base_name

    if not experiment_dir.exists():
        return base_name

    # Buscar siguiente versión disponible
    version = 2
    while True:
        new_name = f"{base_name}_v{version}"
        if not (project_dir / new_name).exists():
            return new_name
        version += 1
        if version > 100:  # Límite de seguridad
            # Usar timestamp si hay demasiadas versiones
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{base_name}_{timestamp}"


def list_existing_experiments(project_dir: Path) -> list:
    """Lista experimentos existentes en el directorio del proyecto."""
    if not project_dir.exists():
        return []

    experiments = []
    for item in project_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Verificar que tenga estructura de experimento YOLO
            if (item / "weights").exists() or (item / "args.yaml").exists():
                experiments.append(item.name)

    return sorted(experiments)


def save_training_config(output_dir: Path, args: argparse.Namespace, env_info: Dict, command_line: str):
    """Guarda la configuración del experimento para reproducibilidad."""
    config = {
        "timestamp": datetime.now().isoformat(),
        "experiment_name": args.name,
        "command": command_line,  # Comando exacto para reproducir
        "dataset": str(args.dataset_dir),
        "model": args.model,
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch,
            "image_size": args.imgsz,
            "patience": args.patience,
            "device": args.device,
            "resume": args.resume
        },
        "environment": env_info
    }

    config_path = output_dir / "training_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    logger.info(f"Configuración guardada en: {config_path}")


def main():
    # Importar configuración por defecto
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from configs import dataset_config as cfg
        default_model = cfg.MODEL_BASE
        default_epochs = cfg.EPOCHS
        default_batch = cfg.BATCH_SIZE
        default_imgsz = cfg.IMAGE_SIZE
        default_name = cfg.TRAINING_NAME
        default_patience = cfg.PATIENCE
        default_dataset = str(cfg.OUTPUT_DIR)
    except ImportError:
        logger.warning("No se pudo importar configs/dataset_config.py, usando valores por defecto")
        default_model = "models/pretrained/yolo11l-obb.pt"
        default_epochs = 100
        default_batch = 16
        default_imgsz = 320
        default_name = "marras_detection"
        default_patience = 25
        default_dataset = "./data/datasets/yolo_marras"

    # Argumentos
    parser = argparse.ArgumentParser(
        description="Entrena un modelo YOLOv11-OBB para detección de marras",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Usar configuración por defecto
  python scripts/train.py --dataset-dir ./data/datasets/yolo_marras

  # Entrenamiento personalizado
  python scripts/train.py \\
    --dataset-dir ./data/datasets/yolo_marras \\
    --model models/pretrained/yolo11x-obb.pt \\
    --epochs 150 \\
    --batch 8 \\
    --name experimento_v2
        """
    )

    parser.add_argument("--dataset-dir", type=str, default=default_dataset,
                        help=f"Ruta al dataset (default: {default_dataset})")
    parser.add_argument("--model", type=str, default=default_model,
                        help=f"Modelo base YOLO (default: {default_model})")
    parser.add_argument("--epochs", type=int, default=default_epochs,
                        help=f"Número de épocas (default: {default_epochs})")
    parser.add_argument("--batch", type=int, default=default_batch,
                        help=f"Tamaño del batch (default: {default_batch})")
    parser.add_argument("--imgsz", type=int, default=default_imgsz,
                        help=f"Tamaño de imagen (default: {default_imgsz})")
    parser.add_argument("--name", type=str, default=default_name,
                        help=f"Nombre del experimento (default: {default_name})")
    parser.add_argument("--patience", type=int, default=default_patience,
                        help=f"Paciencia para early stopping (default: {default_patience})")
    parser.add_argument("--device", type=str, default="",
                        help="Dispositivo (cuda:0, cpu, etc.). Vacío = auto-detección")
    parser.add_argument("--resume", action="store_true",
                        help="Resumir entrenamiento desde último checkpoint")
    parser.add_argument("--overwrite", action="store_true",
                        help="Permitir sobreescribir experimento existente (por defecto crea nueva versión)")
    parser.add_argument("--list-experiments", action="store_true",
                        help="Listar experimentos existentes y salir")

    args = parser.parse_args()

    # Comando exacto usado (para reproducibilidad)
    command_line = " ".join(sys.argv)

    # Listar experimentos si se solicita
    if args.list_experiments:
        project_dir = TRAINING_RESULTS_DIR
        experiments = list_existing_experiments(project_dir)

        if experiments:
            print("\n=== Experimentos Existentes ===")
            for exp in experiments:
                exp_path = project_dir / exp
                # Intentar obtener timestamp
                config_path = exp_path / "training_config.json"
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        cfg = json.load(f)
                        timestamp = cfg.get('timestamp', 'N/A')
                        epochs = cfg.get('hyperparameters', {}).get('epochs', 'N/A')
                        print(f"  - {exp} (Creado: {timestamp[:19]}, Épocas: {epochs})")
                else:
                    print(f"  - {exp}")
        else:
            print("\nNo se encontraron experimentos existentes.")

        sys.exit(0)

    # Banner y verificación del entorno
    print_banner()
    start_time = datetime.now()
    env_info = check_environment()

    # Validar dataset
    logger.info("\n=== Validando Dataset ===")
    ds_path = Path(args.dataset_dir)
    if not ds_path.is_absolute():
        ds_path = (PROJECT_ROOT / ds_path).resolve()

    if not ds_path.exists():
        logger.error(f"El directorio del dataset no existe: {ds_path}")
        logger.error("Falta ejecutar previamente: python scripts/generar_parches.py")
        sys.exit(1)

    is_valid, msg = validate_dataset(ds_path)
    if not is_valid:
        logger.error(f"Dataset inválido: {msg}")
        sys.exit(1)

    logger.info(f"  [OK] {msg}")

    # Estadísticas del dataset
    stats = get_dataset_stats(ds_path)
    logger.info("  Estadísticas del dataset:")
    for key, value in stats.items():
        logger.info(f"    {key}: {value}")

    # Obtener mapa de clases
    try:
        class_map = get_class_map(ds_path)
        logger.info(f"  [OK] Clases detectadas: {class_map}")
    except (FileNotFoundError, KeyError) as e:
        logger.error(str(e))
        sys.exit(1)

    # Crear YAML
    yaml_path = create_yaml(ds_path, class_map)

    # Gestión de versiones de entrenamientos
    logger.info("\n=== Configuración del Entrenamiento ===")
    project_dir = TRAINING_RESULTS_DIR
    original_name = args.name

    # Verificar si ya existe y manejar versionado
    experiment_exists = (project_dir / args.name).exists()

    if experiment_exists and not args.overwrite and not args.resume:
        # Auto-versionar para no pisar entrenamientos anteriores
        args.name = get_unique_experiment_name(args.name, project_dir)
        logger.info(f"  ℹ El nombre '{original_name}' ya existe, creando: '{args.name}'")
    elif experiment_exists and args.resume:
        logger.info(f"  ↻ Resumiendo entrenamiento: '{args.name}'")

    logger.info(f"  Dataset: {ds_path}")
    model_path = Path(args.model)
    if not model_path.is_absolute():
        model_path = (PROJECT_ROOT / model_path).resolve()
    args.model = str(model_path)
    logger.info(f"  Modelo base: {model_path}")
    logger.info(f"  Épocas: {args.epochs}")
    logger.info(f"  Batch size: {args.batch}")
    logger.info(f"  Image size: {args.imgsz}")
    logger.info(f"  Patience: {args.patience}")
    logger.info(f"  Nombre: {args.name}")
    logger.info(f"  Dispositivo: {args.device if args.device else 'auto'}")

    # Preparar directorio de salida
    output_dir = project_dir / args.name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Guardar configuración para reproducibilidad
    save_training_config(output_dir, args, env_info, command_line)

    # Iniciar entrenamiento
    logger.info("\n=== Iniciando Entrenamiento ===")
    logger.info("Este proceso puede tardar varias horas dependiendo del hardware...")

    try:
        model = YOLO(str(model_path))

        results = model.train(
            data=str(yaml_path),
            task='obb',
            project=str(TRAINING_RESULTS_DIR),
            name=args.name,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            patience=args.patience,
            device=args.device if args.device else None,
            exist_ok=True,
            resume=args.resume,
            verbose=True
        )

        # Resumen final
        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("\n" + "="*60)
        logger.info("[OK] ENTRENAMIENTO COMPLETADO")
        logger.info("="*60)
        logger.info(f"Tiempo total: {duration}")
        logger.info(f"Resultados guardados en: {output_dir}")
        logger.info(f"  - Mejor modelo: {output_dir}/weights/best.pt")
        logger.info(f"  - Último modelo: {output_dir}/weights/last.pt")
        logger.info(f"  - Métricas: {output_dir}/results.csv")
        logger.info(f"  - Gráficos: {output_dir}/results.png")
        logger.info("="*60)

        # Mostrar métricas finales si están disponibles
        results_csv = output_dir / "results.csv"
        if results_csv.exists():
            logger.info("\nPara ver las métricas detalladas:")
            logger.info(f"  cat {results_csv}")

    except Exception as e:
        logger.error(f"\n[ERROR] Error durante el entrenamiento: {e}")
        logger.exception("Detalles del error:")
        sys.exit(1)


if __name__ == "__main__":
    main()
