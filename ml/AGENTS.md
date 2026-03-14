# Repository Guidelines

## Project Structure & Module Organization
- `scripts/` agrupa los entrypoints (`generar_parches.py`, `train.py`, `compare_models.py`, `evaluate_on_test.py`); sitúa utilidades compartidas en funciones dentro de estos archivos.
- `configs/dataset_config.py` centraliza rutas y parámetros; modifica ahí los paths en lugar de duplicarlos.
- `data/raw/` y `data/datasets/` guardan insumos pesados fuera de git; `models/` conserva checkpoints y `results/` organiza métricas por experimento.
- Reserva `notebooks/` para análisis exploratorio y mueve hallazgos estables a `scripts/`.

## Build, Test, and Development Commands
- `pip install -r requirements.txt` instala dependencias base de visión y geoespacial.
- `python scripts/generar_parches.py` genera el dataset YOLO en `data/datasets/yolo_marras/` y produce `patcher_report.json`.
- `python scripts/train.py --dataset-dir ./data/datasets/yolo_marras --epochs 100` entrena un modelo YOLO11-OBB almacenando pesos y métricas en `results/vineGAPdetect_Training/`.
- `python scripts/compare_models.py` orquesta comparativas multi-parámetro; usa `--regenerate-report` para recalcular métricas sin reentrenar.
- `python scripts/evaluate_on_test.py` valida el mejor checkpoint sobre el conjunto de test y exporta `results/test_evaluation.csv`.

## Coding Style & Naming Conventions
- Código en Python 3.x con indentación de 4 espacios, imports ordenados estándar y tipado opcional como se observa en `scripts/generar_parches.py`.
- Prefiere funciones puras y dataclasses para configuraciones; reutiliza `logging` en lugar de `print` para trazabilidad en ejecuciones largas.
- Nombra experimentos con `--name` (ej. `marras_exp1`) para mantener carpetas limpias en `results/`. Usa snake_case para variables y archivos Python.

## Testing Guidelines
- No hay suite unitaria formal; valida cambios ejecutando `python scripts/generar_parches.py` con un subconjunto representativo y revisa `patcher_report.json`.
- Tras ajustes en entrenamiento, lanza un ciclo corto (`python scripts/train.py --epochs 3 --imgsz 320`) para asegurar compatibilidad.
- Usa `python scripts/evaluate_on_test.py` como verificación mínima antes de subir modelos y adjunta métricas clave (precision, recall, mAP) en la discusión de cambios.

## Commit & Pull Request Guidelines
- Usa mensajes cortos en español en modo indicativo (ej. `ajusta rutas de datos satelitales`) y agrupa cambios relacionados en un solo commit.
- Las PR deben describir propósito, parámetros modificados en `configs/`, datasets generados y adjuntar rutas/ID de experimento relevantes en `results/`.
- Incluye evidencia de ejecución (fragmento de log o métricas resumidas) y enlaza issues o tareas internas cuando existan.

## Data & Configuration Practices
- Nunca comprometas datos fuente privados (`data/raw/`, `models/trained/`). Usa rutas relativas y documenta requisitos externos en README o la PR.
- Antes de ejecutar scripts intensivos, confirma que `configs/dataset_config.py` apunta a rutas locales válidas y que `MAX_WORKERS` respeta la máquina donde se correrá el pipeline.
