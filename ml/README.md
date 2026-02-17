# ML Module

Parte experimental de `vineGAPdetect`: generación de dataset, entrenamiento, comparación de configuraciones, evaluación en test y explicabilidad offline.

## Estructura

```text
ml/
├── archive/
│   └── legacy_visual_demo.py      # Demo Streamlit archivada (legacy)
├── configs/
│   └── dataset_config.py          # Configuración centralizada del pipeline ML
├── data/
│   ├── raw/                       # Rasters y vectores originales
│   └── datasets/                  # Datasets YOLO generados
├── models/
│   ├── pretrained/                # Pesos base descargados
│   └── trained/                   # Modelo entrenado usado por la app
├── results/                       # Resultados de entrenamientos y comparativas
├── scripts/
│   ├── generar_parches.py         # Construcción de dataset YOLO-OBB
│   ├── train.py                   # Entrenamiento YOLO-OBB
│   ├── compare_models.py          # Comparación sistemática de configuraciones
│   ├── evaluate_on_test.py        # Evaluación final sobre el split de test
│   ├── explainability_cam.py      # Generación offline de Eigen-CAM / Grad-CAM
│   └── yolo_cam/                  # Librería local CAM adaptada a Ultralytics/OBB
└── requirements.txt
```

## Qué se usa en la app actual

- El backend carga el modelo desde `ml/models/trained/best.pt`.
- La explicabilidad de la app web usa `ml/scripts/yolo_cam/`.
- Los demás scripts de `ml/scripts/` forman el pipeline experimental y de reproducibilidad del TFG, pero no se ejecutan directamente desde FastAPI o React.

## Instalación

Desde `ml/`:

```bash
pip install -r requirements.txt
```

## Configuración

La configuración central está en [configs/dataset_config.py](./configs/dataset_config.py).

Por defecto usa rutas relativas a `ml/`, pero puedes sobrescribirlas con variables de entorno:

- `VINEGAP_RASTER_DIR`
- `VINEGAP_VECTOR_DIR`
- `VINEGAP_OUTPUT_DIR`

## Flujo recomendado para el TFG

### 1. Generar dataset

```bash
python scripts/generar_parches.py
```

Overrides útiles:

```bash
python scripts/generar_parches.py --patch-size 640 --output-dir ./data/datasets/yolo_marras_640px
```

Salida principal:

- `data/datasets/<dataset>/images/{train,validation,test}`
- `data/datasets/<dataset>/labels/{train,validation,test}`
- `data/datasets/<dataset>/dataset.yaml`
- `data/datasets/<dataset>/patcher_report.json`
- `data/datasets/<dataset>/split_manifest.json`

Para regenerar un dataset desde cero y evitar mezclar salidas antiguas:

```bash
python scripts/generar_parches.py --patch-size 640 --output-dir ./data/datasets/yolo_marras_640px --clean-output
```

### 2. Entrenar modelo

```bash
python scripts/train.py --dataset-dir ./data/datasets/yolo_marras
```

Ejemplo:

```bash
python scripts/train.py \
  --dataset-dir ./data/datasets/yolo_marras \
  --model models/pretrained/yolo11l-obb.pt \
  --epochs 100 \
  --batch 16 \
  --imgsz 320 \
  --name marras_exp1
```

Resultados:

- `results/vineGAPdetect_Training/<experimento>/weights/best.pt`
- `results/vineGAPdetect_Training/<experimento>/results.csv`
- `results/vineGAPdetect_Training/<experimento>/training_config.json`

### 3. Comparar configuraciones

```bash
python scripts/compare_models.py
```

Este script:

- genera datasets para varios tamaños de parche
- entrena configuraciones Nano y Large
- guarda progreso parcial en `results/comparison_partial.json`
- genera `results/comparison_report.csv` y `results/comparison_full.json`
- usa `--clean-output` al regenerar cada dataset experimental

Para regenerar solo el informe:

```bash
python scripts/compare_models.py --regenerate-report
```

Para lanzar la comparativa completa sin confirmación interactiva:

```bash
python scripts/compare_models.py --yes
```

### 4. Evaluación final en test

```bash
python scripts/evaluate_on_test.py
```

Genera:

- `results/test_evaluation.csv`
- `results/test_evaluation.json`

### 5. Explicabilidad offline

Eigen-CAM:

```bash
python scripts/explainability_cam.py --image ./data/datasets/yolo_marras/images/test --method eigencam
```

Grad-CAM:

```bash
python scripts/explainability_cam.py --image ./data/datasets/yolo_marras/images/test --method gradcam
```

Opciones útiles:

- `--model`
- `--output-dir`
- `--target-layers`
- `--conf-threshold`
- `--imgsz`

## Notas

- `archive/legacy_visual_demo.py` se conserva solo como referencia histórica.
- `scripts/yolo_cam/` es una librería local compartida con el backend para CAM sobre modelos OBB de Ultralytics.
- Si vas a usar resultados de esta carpeta en la memoria del TFG, toma como referencia los artefactos de `ml/results/` y no salidas temporales fuera de esa ruta.

## Evidencia de reproducibilidad

Antes de ejecutar los experimentos en el equipo de entrenamiento, guarda el entorno:

```bash
python scripts/capture_environment.py
```

Esto crea `results/environment/` con versión de Python, `pip freeze`, estado de Git y `nvidia-smi` si está disponible.

Para ejecutar el protocolo completo desde cero en el equipo con GPU:

```bash
python scripts/run_full_experiment.py
```

El orquestador guarda `results/full_experiment_manifest.json` y genera XAI sobre el mejor modelo en test. Si prefieres omitir XAI en la primera tirada:

```bash
python scripts/run_full_experiment.py --skip-xai
```
