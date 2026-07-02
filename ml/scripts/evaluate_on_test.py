#!/usr/bin/env python3
"""
Script de Evaluación en Test Set - vineGAPdetect

Valida todos los modelos best.pt en el conjunto de TEST (no validación).
Esto proporciona métricas imparciales del rendimiento real de cada modelo.

Uso:
    python scripts/evaluate_on_test.py
"""
import json
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any
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
    """Imprime banner de inicio."""
    print("vineGAPdetect - evaluacion en test")


def extract_metrics(results: Any) -> Dict[str, float]:
    metrics = {
        'Precision': 0.0,
        'Recall': 0.0,
        'mAP@50': 0.0,
        'mAP@50-95': 0.0,
    }

    metrics_obj = None
    for attr in ("obb", "box"):
        candidate = getattr(results, attr, None)
        if candidate is not None and hasattr(candidate, "map50"):
            metrics_obj = candidate
            break

    if metrics_obj is None:
        return metrics

    metrics['Precision'] = round(float(metrics_obj.p), 4) if hasattr(metrics_obj, 'p') else 0.0
    metrics['Recall'] = round(float(metrics_obj.r), 4) if hasattr(metrics_obj, 'r') else 0.0
    metrics['mAP@50'] = round(float(metrics_obj.map50), 4) if hasattr(metrics_obj, 'map50') else 0.0
    metrics['mAP@50-95'] = round(float(metrics_obj.map), 4) if hasattr(metrics_obj, 'map') else 0.0
    return metrics


def validate_on_test(experiment_name: str, dataset_dir: str) -> Dict[str, float]:
    """
    Valida un modelo en el conjunto de TEST.

    Args:
        experiment_name: Nombre del experimento
        dataset_dir: Directorio del dataset

    Returns:
        Dict con métricas en test
    """
    best_model_path = TRAINING_RESULTS_DIR / experiment_name / "weights" / "best.pt"

    # Convertir dataset_dir a ruta absoluta si es relativa
    dataset_path = Path(dataset_dir)
    if not dataset_path.is_absolute():
        dataset_path = (PROJECT_ROOT / dataset_path).resolve()

    dataset_yaml = dataset_path / "dataset.yaml"

    # Verificar que existe el conjunto de test
    test_images_dir = dataset_path / "images" / "test"

    metrics = {
        'Precision': 0.0,
        'Recall': 0.0,
        'mAP@50': 0.0,
        'mAP@50-95': 0.0,
        'Test_Images': 0
    }

    if not best_model_path.exists():
        logger.warning(f"  AVISO Modelo best.pt no encontrado para {experiment_name}")
        return metrics

    if not dataset_yaml.exists():
        logger.warning(f"  AVISO Dataset YAML no encontrado: {dataset_yaml}")
        return metrics

    if not test_images_dir.exists():
        logger.warning(f"  AVISO Directorio test no encontrado: {test_images_dir}")
        return metrics

    try:
        # Contar imágenes de test
        test_images = list(test_images_dir.glob("*.png"))
        metrics['Test_Images'] = len(test_images)

        if len(test_images) == 0:
            logger.warning(f"  AVISO No hay imágenes en test para {experiment_name}")
            return metrics

        # Cargar modelo
        model = YOLO(str(best_model_path))

        # Validar en el conjunto de TEST
        logger.info(f"  Validando {experiment_name} en TEST ({len(test_images)} imágenes)...")
        results = model.val(
            data=str(dataset_yaml),
            split='test',  # <- Importante: usar split test
            batch=8,
            verbose=False
        )

        metrics.update(extract_metrics(results))

        logger.info(f"    [OK] mAP@50-95: {metrics['mAP@50-95']:.4f}")

    except Exception as e:
        logger.warning(f"  [ERROR] Error validando {experiment_name}: {e}")

    return metrics


def main():
    print_banner()

    # Leer resultados parciales
    partial_path = RESULTS_DIR / "comparison_partial.json"

    if not partial_path.exists():
        logger.error(f"No se encontró {partial_path}")
        logger.error("Falta ejecutar previamente: python scripts/compare_models.py")
        return

    with open(partial_path, 'r') as f:
        results = json.load(f)

    logger.info(f"[OK] Cargados {len(results)} resultados\n")

    # Filtrar solo entrenamientos exitosos
    training_results = [r for r in results if 'config' in r and r.get('success')]

    if not training_results:
        logger.error("No hay entrenamientos exitosos para evaluar")
        return

    logger.info(f"Evaluando {len(training_results)} modelos en conjunto de TEST\n")
    logger.info("="*70)

    # Evaluar cada modelo en test
    test_results = []

    for i, result in enumerate(training_results, 1):
        experiment_name = result["name"]
        dataset_dir = result['config']['dataset_dir']

        logger.info(f"\n[{i}/{len(training_results)}] {experiment_name}")

        # Evaluar en test
        test_metrics = validate_on_test(experiment_name, dataset_dir)

        # Crear fila del reporte
        row = {
            "Experimento": experiment_name,
            "Modelo": "Nano" if "nano" in experiment_name else "Large",
            "Tamaño Parche": f"{result['config']['imgsz']}px",
            "Batch Size": result['config']['batch'],
            "Imágenes Test": test_metrics['Test_Images'],
            "Precision": test_metrics['Precision'],
            "Recall": test_metrics['Recall'],
            "mAP@50": test_metrics['mAP@50'],
            "mAP@50-95": test_metrics['mAP@50-95'],
        }

        test_results.append(row)

    # Crear DataFrame
    df = pd.DataFrame(test_results)

    # Guardar CSV
    output_path = RESULTS_DIR / "test_evaluation.csv"
    df.to_csv(output_path, index=False)

    logger.info("\n" + "="*70)
    logger.info("RESULTADOS EN TEST SET")
    logger.info("="*70)

    # Mostrar tabla completa
    print("\n" + df.to_string(index=False))

    # Guardar también JSON con detalles
    test_summary = {
        "total_models": len(training_results),
        "results": test_results
    }

    json_path = RESULTS_DIR / "test_evaluation.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(test_summary, f, indent=2, ensure_ascii=False)

    # Estadísticas
    logger.info("\n" + "="*70)
    logger.info("ESTADÍSTICAS")
    logger.info("="*70)
    logger.info(f"  Total modelos evaluados: {len(training_results)}")

    if 'mAP@50-95' in df.columns and len(df) > 0:
        # Filtrar filas con métricas válidas
        valid_df = df[df['mAP@50-95'] > 0]

        if len(valid_df) > 0:
            # Mejor modelo
            best_idx = valid_df['mAP@50-95'].idxmax()
            best = df.iloc[best_idx]

            logger.info(f"\n MEJOR MODELO EN TEST (mAP@50-95):")
            logger.info(f"  Experimento: {best['Experimento']}")
            logger.info(f"  Modelo: {best['Modelo']}")
            logger.info(f"  Tamaño Parche: {best['Tamaño Parche']}")
            logger.info(f"  mAP@50-95: {best['mAP@50-95']:.4f}")
            logger.info(f"  Precision: {best['Precision']:.4f}")
            logger.info(f"  Recall: {best['Recall']:.4f}")

            # Comparar nano vs large
            logger.info("\n📊 COMPARACIÓN NANO vs LARGE:")
            nano_df = valid_df[valid_df['Modelo'] == 'Nano']
            large_df = valid_df[valid_df['Modelo'] == 'Large']

            if len(nano_df) > 0:
                avg_nano = nano_df['mAP@50-95'].mean()
                logger.info(f"  Nano  - mAP@50-95 promedio: {avg_nano:.4f}")

            if len(large_df) > 0:
                avg_large = large_df['mAP@50-95'].mean()
                logger.info(f"  Large - mAP@50-95 promedio: {avg_large:.4f}")

    logger.info("\n" + "="*70)
    logger.info("[OK] EVALUACIÓN COMPLETADA")
    logger.info("="*70)
    logger.info(f"\nResultados guardados en:")
    logger.info(f"  - CSV: {output_path}")
    logger.info(f"  - JSON: {json_path}")


if __name__ == "__main__":
    main()
