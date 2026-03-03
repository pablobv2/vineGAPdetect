# -*- coding: utf-8 -*-
"""
Script de Comparación de Configuraciones - vineGAPdetect
Ejecuta múltiples entrenamientos con diferentes tamaños de parche y modelos.

Objetivo: Determinar el tamaño óptimo de parche para detección de marras.

Comparación sistemática:
- Modelos: nano (rápido) y large (preciso)
- Tamaños de parche: 256, 320, 416, 512, 640

Uso:
    python scripts/compare_models.py

Los resultados se guardan en results/vineGAPdetect_Training/ con nombres descriptivos.
Al finalizar, genera un reporte comparativo en results/comparison_report.csv
"""

import subprocess
import sys
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
RESULTS_DIR = PROJECT_ROOT / "results"
TRAINING_RESULTS_DIR = RESULTS_DIR / "vineGAPdetect_Training"


# ============================================================================
# CONFIGURACIÓN DE COMPARACIONES
# ============================================================================

# Tamaños de parche a probar
PATCH_SIZES = [256, 320, 416, 512, 640]

# Modelos a comparar
MODELS = {
    "nano": {
        "path": "models/pretrained/yolo11n-obb.pt",
        "batch_sizes": {256: 24, 320: 16, 416: 12, 512: 8, 640: 6}
    },
    "large": {
        "path": "models/pretrained/yolo11l-obb.pt",
        "batch_sizes": {256: 16, 320: 12, 416: 8, 512: 6, 640: 4}
    }
}

# Base para datasets (se generará uno por tamaño de parche)
DATASET_BASE_DIR = "./data/datasets"

# Configuración de entrenamiento
EPOCHS = 100
PATIENCE = 25
DEVICE = ""  # Vacío = auto-detección


# Generar configuraciones automáticamente
def generate_configurations():
    """
    Genera configuraciones agrupadas por tamaño de parche.
    Cada grupo incluye la generación del dataset + entrenamientos.
    """
    configs = []

    for patch_size in PATCH_SIZES:
        dataset_dir = f"{DATASET_BASE_DIR}/yolo_marras_{patch_size}px"

        # Configuración para generar dataset
        dataset_config = {
            "type": "generate_dataset",
            "patch_size": patch_size,
            "dataset_dir": dataset_dir,
            "name": f"dataset_{patch_size}px"
        }
        configs.append(dataset_config)

        # Configuraciones para entrenar con este dataset
        for model_name, model_info in MODELS.items():
            train_config = {
                "type": "train",
                "name": f"{model_name}_{patch_size}px",
                "description": f"YOLO11-{model_name} con parches {patch_size}x{patch_size}",
                "model": model_info["path"],
                "dataset_dir": dataset_dir,
                "imgsz": patch_size,
                "batch": model_info["batch_sizes"][patch_size],
                "epochs": EPOCHS,
            }
            configs.append(train_config)

    return configs


CONFIGURATIONS = generate_configurations()


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def print_banner():
    """Imprime banner de inicio."""
    banner = """
    ╔════════════════════════════════════════════════════════════╗
    ║       vineGAPdetect - Comparación Tamaños de Parche            ║
    ║          Modelos: Nano vs Large | Parches: 5 Tamaños      ║
    ╚════════════════════════════════════════════════════════════╝
    """
    print(banner)


def generate_dataset(patch_size: int, output_dir: str) -> Dict[str, Any]:
    """
    Genera un dataset con el tamaño de parche especificado.

    Returns:
        Dict con información del resultado
    """
    logger.info("\n" + "="*70)
    logger.info(f"GENERANDO DATASET: Parches de {patch_size}x{patch_size} px")
    logger.info(f"Directorio: {output_dir}")
    logger.info("="*70)

    # Construir comando con argumentos CLI
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "generar_parches.py"),
        "--patch-size", str(patch_size),
        "--output-dir", output_dir,
        "--clean-output",
    ]

    logger.info(f"Comando: {' '.join(cmd)}")
    start_time = datetime.now()

    try:
        # Ejecutar generación
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,
            text=True,
            cwd=PROJECT_ROOT,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"✓ Dataset generado en {duration/60:.1f} minutos")

        return {
            "name": f"dataset_{patch_size}px",
            "success": True,
            "duration_seconds": duration,
            "patch_size": patch_size,
            "output_dir": output_dir
        }

    except subprocess.CalledProcessError as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error(f"✗ Error generando dataset")

        return {
            "name": f"dataset_{patch_size}px",
            "success": False,
            "duration_seconds": duration,
            "error": str(e)
        }


def validate_dataset(dataset_path: Path) -> bool:
    """Valida que el dataset exista y tenga estructura correcta."""
    if not dataset_path.exists():
        return False

    required = [
        dataset_path / "images" / "train",
        dataset_path / "labels" / "train",
    ]

    for req in required:
        if not req.exists():
            return False

    return True


def run_training(config: Dict[str, Any], dataset_dir: str) -> Dict[str, Any]:
    """
    Ejecuta un entrenamiento con la configuración especificada.

    Returns:
        Dict con información del resultado (success, duration, metrics, etc.)
    """
    logger.info("\n" + "="*70)
    logger.info(f"INICIANDO: {config['name']}")
    logger.info(f"{config['description']}")
    logger.info("="*70)

    # Construir comando
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "train.py"),
        "--dataset-dir", dataset_dir,
        "--model", config["model"],
        "--imgsz", str(config["imgsz"]),
        "--batch", str(config["batch"]),
        "--epochs", str(config["epochs"]),
        "--patience", str(PATIENCE),
        "--name", config["name"],
    ]

    if DEVICE:
        cmd.extend(["--device", DEVICE])

    logger.info(f"Comando: {' '.join(cmd)}")

    # Ejecutar entrenamiento
    start_time = datetime.now()

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,  # Mostrar output en tiempo real
            text=True,
            cwd=PROJECT_ROOT,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"✓ Completado: {config['name']} en {duration/60:.1f} minutos")

        return {
            "name": config["name"],
            "description": config["description"],
            "success": True,
            "duration_seconds": duration,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "config": config
        }

    except subprocess.CalledProcessError as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error(f"✗ Error en: {config['name']}")
        logger.error(f"Código de salida: {e.returncode}")

        return {
            "name": config["name"],
            "description": config["description"],
            "success": False,
            "duration_seconds": duration,
            "error": str(e),
            "config": config
        }


def extract_metrics(results: Any) -> Dict[str, float]:
    metrics = {}
    metrics_obj = None

    for attr in ("obb", "box"):
        candidate = getattr(results, attr, None)
        if candidate is not None and hasattr(candidate, "map50"):
            metrics_obj = candidate
            break

    if metrics_obj is None:
        return metrics

    metrics["Precision"] = round(float(metrics_obj.p), 4) if hasattr(metrics_obj, "p") else 0.0
    metrics["Recall"] = round(float(metrics_obj.r), 4) if hasattr(metrics_obj, "r") else 0.0
    metrics["mAP@50"] = round(float(metrics_obj.map50), 4) if hasattr(metrics_obj, "map50") else 0.0
    metrics["mAP@50-95"] = round(float(metrics_obj.map), 4) if hasattr(metrics_obj, "map") else 0.0
    return metrics


def extract_metrics_from_best_model(experiment_name: str, dataset_dir: str) -> Dict[str, float]:
    """
    Valida el mejor modelo (best.pt) y extrae sus métricas.
    Esto es lo más confiable ya que usa las métricas oficiales del modelo guardado.
    """
    from ultralytics import YOLO

    best_model_path = TRAINING_RESULTS_DIR / experiment_name / "weights" / "best.pt"

    # Convertir dataset_dir a ruta absoluta si es relativa
    dataset_path = Path(dataset_dir)
    if not dataset_path.is_absolute():
        dataset_path = (PROJECT_ROOT / dataset_path).resolve()

    dataset_yaml = dataset_path / "dataset.yaml"

    metrics = {}

    if not best_model_path.exists():
        logger.warning(f"Modelo best.pt no encontrado para {experiment_name}")
        return metrics

    if not dataset_yaml.exists():
        logger.warning(f"Dataset YAML no encontrado: {dataset_yaml}")
        return metrics

    try:
        # Cargar modelo
        model = YOLO(str(best_model_path))

        # Validar en el dataset
        logger.info(f"  Validando {experiment_name}...")
        results = model.val(
            data=str(dataset_yaml),
            batch=8,
            verbose=False
        )

        metrics.update(extract_metrics(results))

    except Exception as e:
        logger.warning(f"Error validando {experiment_name}: {e}")

    return metrics


def generate_comparison_report(results: List[Dict[str, Any]], output_path: Path):
    """Genera reporte comparativo de todos los entrenamientos."""
    logger.info("\n" + "="*70)
    logger.info("GENERANDO REPORTE COMPARATIVO")
    logger.info("="*70)

    # Filtrar solo resultados de entrenamiento (no generación de datasets)
    training_results = [r for r in results if 'config' in r]

    if not training_results:
        logger.warning("No hay resultados de entrenamientos para generar reporte")
        return

    # Preparar datos para el reporte
    report_data = []

    for result in training_results:
        experiment_name = result["name"]

        # Datos básicos
        row = {
            "Experimento": experiment_name,
            "Modelo": "Nano" if "nano" in experiment_name else "Large",
            "Tamaño Parche": f"{result['config']['imgsz']}px",
            "Batch Size": result['config']['batch'],
            "Épocas": result['config']['epochs'],
            "Estado": "✓" if result["success"] else "✗",
            "Duración (min)": round(result["duration_seconds"] / 60, 1),
        }

        # Extraer métricas validando el best.pt si el entrenamiento fue exitoso
        if result["success"]:
            dataset_dir = result['config']['dataset_dir']
            metrics = extract_metrics_from_best_model(experiment_name, dataset_dir)
            row.update(metrics)

        report_data.append(row)

    # Crear DataFrame
    df = pd.DataFrame(report_data)

    # Guardar CSV
    df.to_csv(output_path, index=False)
    logger.info(f"\n✓ Reporte guardado en: {output_path}")

    # Mostrar tabla resumida
    print("\n" + "="*80)
    print("RESUMEN COMPARATIVO - TAMAÑOS DE PARCHE")
    print("="*80)

    # Mostrar por modelo si es posible
    if 'mAP@50-95' in df.columns:
        print("\n--- MODELO NANO ---")
        nano_df = df[df['Modelo'] == 'Nano'].sort_values('Tamaño Parche')
        print(nano_df[['Tamaño Parche', 'Batch Size', 'mAP@50-95', 'Precision', 'Recall', 'Duración (min)']].to_string(index=False))

        print("\n--- MODELO LARGE ---")
        large_df = df[df['Modelo'] == 'Large'].sort_values('Tamaño Parche')
        print(large_df[['Tamaño Parche', 'Batch Size', 'mAP@50-95', 'Precision', 'Recall', 'Duración (min)']].to_string(index=False))
    else:
        print(df.to_string(index=False))

    print("="*80 + "\n")

    # Estadísticas generales
    successful = sum(1 for r in training_results if r["success"])
    failed = len(training_results) - successful
    total_time = sum(r["duration_seconds"] for r in training_results)

    logger.info(f"\nEstadísticas de Entrenamientos:")
    logger.info(f"  Total entrenamientos: {len(training_results)}")
    logger.info(f"  Exitosos: {successful}")
    logger.info(f"  Fallidos: {failed}")
    logger.info(f"  Tiempo entrenamientos: {total_time/3600:.2f} horas")

    # Mejor configuración
    if 'mAP@50-95' in df.columns and successful > 0:
        best_idx = df[df['Estado'] == '✓']['mAP@50-95'].idxmax()
        best = df.iloc[best_idx]
        logger.info(f"\n🏆 MEJOR CONFIGURACIÓN (mAP@50-95):")
        logger.info(f"  Experimento: {best['Experimento']}")
        logger.info(f"  Modelo: {best['Modelo']}")
        logger.info(f"  Tamaño Parche: {best['Tamaño Parche']}")
        logger.info(f"  mAP@50-95: {best['mAP@50-95']:.4f}")
        logger.info(f"  Precision: {best['Precision']:.4f}")
        logger.info(f"  Recall: {best['Recall']:.4f}")


def main():
    import argparse

    # Argumentos CLI
    parser = argparse.ArgumentParser(
        description="Comparación sistemática de modelos YOLO",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--regenerate-report", action="store_true",
                        help="Regenerar reporte desde resultados guardados (no entrena)")
    parser.add_argument("--yes", action="store_true",
                        help="Ejecuta el plan completo sin pedir confirmacion interactiva")
    args = parser.parse_args()

    print_banner()

    # Modo: Regenerar reporte desde resultados guardados
    if args.regenerate_report:
        logger.info("=== MODO: Regenerar Reporte ===\n")

        partial_path = RESULTS_DIR / "comparison_partial.json"

        if not partial_path.exists():
            logger.error(f"No se encontró {partial_path}")
            logger.error("Ejecuta primero: python scripts/compare_models.py")
            sys.exit(1)

        with open(partial_path, 'r') as f:
            results = json.load(f)

        logger.info(f"✓ Cargados {len(results)} resultados guardados")
        logger.info("⚠️  Validando cada best.pt (puede tardar unos minutos)...\n")

        # Generar reporte
        report_path = RESULTS_DIR / "comparison_report.csv"
        generate_comparison_report(results, report_path)

        logger.info(f"\n✓ Reporte regenerado exitosamente en: {report_path}")
        return

    # Modo normal: Mostrar plan completo
    logger.info("\n" + "="*70)
    logger.info("PLAN DE COMPARACIÓN")
    logger.info("="*70)
    logger.info(f"Tamaños de parche a probar: {', '.join(map(str, PATCH_SIZES))} px")
    logger.info(f"Modelos por tamaño: Nano, Large")
    logger.info(f"Total tareas: {len(CONFIGURATIONS)} (incluye {len(PATCH_SIZES)} generaciones de datasets + {len(PATCH_SIZES)*2} entrenamientos)\n")

    # Mostrar plan agrupado por tamaño de parche
    for patch_size in PATCH_SIZES:
        print(f"\n--- Parche {patch_size}px ---")
        print(f"  1. Generar dataset → data/datasets/yolo_marras_{patch_size}px")
        print(f"  2. Entrenar YOLO11-nano (batch: {MODELS['nano']['batch_sizes'][patch_size]})")
        print(f"  3. Entrenar YOLO11-large (batch: {MODELS['large']['batch_sizes'][patch_size]})")

    # Confirmación
    logger.info("\n" + "="*70)
    train_configs = [c for c in CONFIGURATIONS if c.get('type') == 'train']
    total_epochs = sum(c['epochs'] for c in train_configs)
    logger.info(f"Épocas totales de entrenamiento: {total_epochs}")
    logger.info(f"Épocas por entrenamiento: {EPOCHS}")
    logger.info(f"Patience: {PATIENCE}")
    logger.info("\n⚠️  Este proceso puede tardar MUCHAS HORAS:")
    logger.info(f"    - Generación datasets: ~{len(PATCH_SIZES)*0.5:.1f}h (estimado)")
    logger.info(f"    - Entrenamientos: ~10-20h (dependiendo de GPU)")
    logger.info(f"    - Total estimado: 12-25 horas")

    if not args.yes:
        response = input("\n¿Continuar? [s/N]: ").strip().lower()
        if response not in ['s', 'si', 'sí', 'y', 'yes']:
            logger.info("Cancelado por el usuario.")
            sys.exit(0)

    # Ejecutar tareas
    logger.info("\n" + "="*70)
    logger.info("COMENZANDO COMPARACIÓN SISTEMÁTICA")
    logger.info("="*70)

    overall_start = datetime.now()
    results = []

    for i, config in enumerate(CONFIGURATIONS, 1):
        logger.info(f"\n{'='*70}")
        logger.info(f"TAREA: [{i}/{len(CONFIGURATIONS)}]")
        logger.info(f"{'='*70}")

        if config['type'] == 'generate_dataset':
            # Generar dataset
            result = generate_dataset(config['patch_size'], config['dataset_dir'])
        else:
            # Entrenar modelo
            result = run_training(config, config['dataset_dir'])

        results.append(result)

        # Guardar resultados parciales (por si se interrumpe)
        partial_path = RESULTS_DIR / "comparison_partial.json"
        partial_path.parent.mkdir(parents=True, exist_ok=True)
        with open(partial_path, 'w') as f:
            json.dump(results, f, indent=2)

        # Mostrar progreso
        completed = sum(1 for r in results if r["success"])
        logger.info(f"\nProgreso: {i}/{len(CONFIGURATIONS)} completados ({completed} exitosos)")

    overall_end = datetime.now()
    overall_duration = (overall_end - overall_start).total_seconds()

    # Generar reporte final
    report_path = RESULTS_DIR / "comparison_report.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    generate_comparison_report(results, report_path)

    # Guardar resultados completos en JSON
    full_results = {
        "start_time": overall_start.isoformat(),
        "end_time": overall_end.isoformat(),
        "duration_seconds": overall_duration,
        "configurations": CONFIGURATIONS,
        "results": results
    }

    json_path = RESULTS_DIR / "comparison_full.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(full_results, f, indent=2, ensure_ascii=False)

    logger.info(f"\n✓ Resultados completos guardados en: {json_path}")
    logger.info(f"✓ Tiempo total de comparación: {overall_duration/3600:.2f} horas")
    logger.info("\n" + "="*70)
    logger.info("🎉 COMPARACIÓN COMPLETADA")
    logger.info("="*70)
    logger.info(f"\nRevisa los resultados en:")
    logger.info(f"  - CSV: {report_path}")
    logger.info(f"  - JSON: {json_path}")
    logger.info(f"  - Entrenamientos: results/vineGAPdetect_Training/")


if __name__ == "__main__":
    main()
