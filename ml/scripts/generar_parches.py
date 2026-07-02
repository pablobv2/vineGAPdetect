# -*- coding: utf-8 -*-
"""
Script de creación de parches y etiquetas YOLOv11-OBB.

Este script permite generar un dataset para entrenar un modelo que detecte una única
clase de interés y filtrar artefactos en los bordes.

"""

import sys
import json
import logging
import warnings
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import asdict, dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed
from logging.handlers import RotatingFileHandler

import numpy as np
import cv2
from tqdm import tqdm
from PIL import Image

warnings.filterwarnings('ignore', category=UserWarning)

# --- CONFIGURACIÓN Y CLASES DE DATOS ---
@dataclass
class PatcherConfig:
    raster_dir: Path
    vector_dir: Path
    output_dir: Path
    patch_size_pixels: int = 640
    patch_overlap: float = 0.5
    skip_empty_patches: bool = True
    max_workers: int = 16
    validation_split: float = 0.15
    test_split: float = 0.15
    random_seed: int = 42
    merge_overlapping_bboxes: bool = True
    bbox_enlargement_factor: float = 0.25
    
    # --- PARÁMETRO PARA EL MODELO ESPECIALISTA ---
    target_class: Optional[str] = None # Ej: 'marras'. Si es None, procesa todas las clases.

    # --- PARÁMETRO PARA FILTRADO DE BORDES ---
    edge_buffer_percentage: float = 0.0 # Ej: 2.0 para un 2% de margen en cada lado.

    def __post_init__(self):
        self.raster_dir = Path(self.raster_dir)
        self.vector_dir = Path(self.vector_dir)
        self.output_dir = Path(self.output_dir)
        for split in ['train', 'validation', 'test']:
            (self.output_dir / 'images' / split).mkdir(parents=True, exist_ok=True)
            (self.output_dir / 'labels' / split).mkdir(parents=True, exist_ok=True)

@dataclass
class PatcherStats:
    total_patches: int = 0
    total_objects: int = 0
    objects_per_class: Dict[str, int] = field(default_factory=dict)
    parcels_processed: int = 0
    errors: int = 0
    tiempo_inicio: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        tiempo_total = (datetime.now() - self.tiempo_inicio).total_seconds()
        return {
            'total_patches_generados': self.total_patches,
            'total_objetos_anotados': self.total_objects,
            'objetos_por_clase': self.objects_per_class,
            'parcelas_procesadas': self.parcels_processed,
            'errores_proceso': self.errors,
            'tiempo_total_segundos': round(tiempo_total, 2)
        }

# --- FUNCIONES AUXILIARES ---
def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('YoloPatcher')
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers(): logger.handlers.clear()
    
    file_handler = RotatingFileHandler(log_dir / 'patch_creation.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

def get_stats_for_single_file(raster_file: Path) -> Dict[str, Tuple[float, float]]:
    import rasterio
    with rasterio.open(raster_file) as src:
        stats = {}
        for i in range(min(src.count, 3)):
            band_idx = i + 1
            data = src.read(band_idx)
            nodata = src.nodata
            valid_data = data[data != nodata] if nodata is not None else data
            if valid_data.size > 0:
                p2, p98 = np.percentile(valid_data, (2, 98))
                stats[f'band_{band_idx}'] = (p2, p98)
    return stats

def _merge_geometries(geoms: List[Any]) -> List[Any]:
    from shapely.ops import unary_union
    if not geoms: return []
    merged = list(geoms)
    while True:
        num_before = len(merged)
        newly_merged, processed = [], [False] * num_before
        for i in range(num_before):
            if processed[i]: continue
            base_geom = merged[i]
            to_merge_indices = [i]
            for j in range(i + 1, num_before):
                if not processed[j] and base_geom.intersects(merged[j]):
                    to_merge_indices.append(j)
            
            if len(to_merge_indices) > 1:
                geoms_to_union = [merged[k] for k in to_merge_indices]
                newly_merged.append(unary_union(geoms_to_union).convex_hull)
                for k in to_merge_indices: processed[k] = True
            else:
                newly_merged.append(base_geom)
                processed[i] = True
        merged = newly_merged
        if len(merged) == num_before: break
    return merged

# --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---
def process_parcel_to_patches(task_data: Tuple) -> Dict[str, Any]:
    import rasterio
    from rasterio.windows import Window
    from rasterio.features import geometry_mask
    import geopandas as gpd
    from shapely.geometry import box

    r_file, v_file, img_dir, lbl_dir, cfg, lbl_col, c_map, img_stats = task_data
    p_stats = {'patches': 0, 'objects': 0, 'objects_per_class': {}, 'errors': 0}
    p_size = cfg.patch_size_pixels

    try:
        with rasterio.open(r_file) as src:
            gdf = gpd.read_file(v_file).to_crs(src.crs)
            if gdf.empty: return p_stats

            if cfg.edge_buffer_percentage > 0:
                raster_bounds = src.bounds
                buffer_x = (raster_bounds.right - raster_bounds.left) * (cfg.edge_buffer_percentage / 100.0)
                buffer_y = (raster_bounds.top - raster_bounds.bottom) * (cfg.edge_buffer_percentage / 100.0)
                safe_area = box(raster_bounds.left + buffer_x, raster_bounds.bottom + buffer_y, raster_bounds.right - buffer_x, raster_bounds.top - buffer_y)
                gdf = gdf[gdf.within(safe_area)]
                if gdf.empty: return p_stats
            
            step = int(p_size * (1 - cfg.patch_overlap))
            for y_off in range(0, src.height, step):
                for x_off in range(0, src.width, step):
                    win = Window(x_off, y_off, p_size, p_size)
                    win_transform = src.window_transform(win)
                    patch_bounds = rasterio.windows.bounds(win, src.transform)
                    
                    patch_geom = box(*patch_bounds)
                    clipped_gdf = gdf.copy()
                    clipped_gdf['geometry'] = clipped_gdf.intersection(patch_geom)
                    clipped_gdf = clipped_gdf[~clipped_gdf.is_empty]
                    
                    if cfg.target_class:
                        clipped_gdf = clipped_gdf[clipped_gdf[lbl_col].astype(str) == cfg.target_class]
                    
                    if cfg.skip_empty_patches and clipped_gdf.empty: continue

                    patch_data = src.read(list(range(1, min(src.count, 3) + 1)), window=win)
                    c, h, w = patch_data.shape
                    if h != p_size or w != p_size:
                        padded = np.zeros((c, p_size, p_size), dtype=patch_data.dtype)
                        padded[:, :h, :w] = patch_data
                        patch_data = padded
                    
                    img_array = np.zeros((p_size, p_size, 3), dtype=np.uint8)
                    for i in range(min(c, 3)):
                        mn, mx = img_stats.get(f'band_{i+1}', (0, 255))
                        if mx > mn: img_array[:, :, i] = np.clip((patch_data[i].astype(float) - mn) / (mx - mn) * 255, 0, 255)
                    if c == 1: img_array[:,:,1] = img_array[:,:,2] = img_array[:,:,0]
                    
                    Image.fromarray(img_array).save(img_dir / f"{v_file.stem}_{y_off}_{x_off}.png")

                    yolo_labels = []
                    geoms_by_class = {c: [] for c in c_map.keys()}
                    for _, row in clipped_gdf.iterrows():
                        class_name = str(row[lbl_col])
                        if class_name in geoms_by_class:
                            geoms_by_class[class_name].append(row.geometry)
                    
                    for class_name, geoms in geoms_by_class.items():
                        if not geoms: continue
                        final_geoms = _merge_geometries([g.buffer(g.length * cfg.bbox_enlargement_factor / 2, cap_style=3) for g in geoms]) if cfg.merge_overlapping_bboxes else geoms
                        
                        for geom in final_geoms:
                            mask = geometry_mask([geom], out_shape=(h, w), transform=win_transform, invert=True)
                            contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                            if not contours: continue
                            
                            rect = cv2.minAreaRect(np.vstack(contours))
                            box_points = np.clip(cv2.boxPoints(rect) / p_size, 0.0, 1.0)
                            
                            yolo_labels.append(f"{c_map[class_name]} " + " ".join(f"{p:.6f}" for p in box_points.flatten()))
                            p_stats['objects'] += 1
                            p_stats['objects_per_class'][class_name] = p_stats['objects_per_class'].get(class_name, 0) + 1
                    
                    if yolo_labels:
                        with open(lbl_dir / f"{v_file.stem}_{y_off}_{x_off}.txt", 'w') as f: f.write("\n".join(yolo_labels))
                        p_stats['patches'] += 1
    except Exception as e:
        logging.getLogger('YoloPatcher').error(f"Error procesando {v_file.name}: {e}")
        p_stats['errors'] += 1
    return p_stats

# --- CLASE ORQUESTADORA ---
class YoloPatcher:
    def __init__(self, config: PatcherConfig, logger: logging.Logger):
        self.cfg, self.log, self.stats = config, logger, PatcherStats()
        self.class_map = {}
        self.split_manifest = {}
        self.unmatched_vectors = []
        self.unmatched_rasters = []
        self.label_column = None

    def process(self):
        import geopandas as gpd
        self.log.info(f"=== INICIANDO PATCHER v5.5 (Especialista: {self.cfg.target_class or 'Desactivado'}) ===")
        raster_map = {
            f.stem.replace('-RGB', ''): f
            for f in sorted(self.cfg.raster_dir.glob("*.tif"))
            if not f.name.endswith('.aux.xml')
        }
        vector_files = sorted(self.cfg.vector_dir.glob("*.gpkg"))
        self.log.info("MODO ESTÁNDAR: Se procesarán todas las parejas raster-vector encontradas por nombre.")

        if not raster_map or not vector_files:
            self.log.error("No se encontraron archivos raster/vector para procesar. Comprobar las rutas configuradas.")
            return

        label_col = None
        all_class_names = set()
        for vfile in tqdm(vector_files, desc="Detectando clases de todos los archivos"):
            try:
                gdf_sample = gpd.read_file(vfile, rows=10)
                if not label_col:
                    label_col = next((c for c in ['marras', 'clase', 'label'] if c in gdf_sample.columns), None)
                if label_col:
                    all_class_names.update(gdf_sample[label_col].astype(str).unique())
            except Exception:
                self.log.warning(f"No se pudo leer {vfile.name} para detectar clases.")
        
        if not label_col: raise ValueError("No se encontró una columna de etiquetas válida.")
        
        self.label_column = label_col

        if self.cfg.target_class:
            if self.cfg.target_class not in all_class_names:
                raise ValueError(f"La clase objetivo '{self.cfg.target_class}' no se encontró en el dataset.")
            final_classes = [self.cfg.target_class]
        else:
            final_classes = sorted(list(all_class_names))
        
        self.class_map = {name: i for i, name in enumerate(final_classes)}
        self.log.info(f"Mapa de clases que se utilizará: {self.class_map}")

        matched_vector_files = [vf for vf in vector_files if vf.stem in raster_map]
        self.unmatched_vectors = [vf.name for vf in vector_files if vf.stem not in raster_map]
        matched_vector_stems = {vf.stem for vf in matched_vector_files}
        self.unmatched_rasters = [path.name for stem, path in raster_map.items() if stem not in matched_vector_stems]

        if self.unmatched_vectors:
            self.log.warning(f"Vectores sin raster emparejado: {len(self.unmatched_vectors)}")
        if self.unmatched_rasters:
            self.log.warning(f"Rasters sin vector emparejado: {len(self.unmatched_rasters)}")
        if not matched_vector_files:
            self.log.error("No hay parejas raster-vector emparejadas por nombre base.")
            return

        np.random.seed(self.cfg.random_seed)
        np.random.shuffle(matched_vector_files)
        n_val = int(len(matched_vector_files) * self.cfg.validation_split)
        n_test = int(len(matched_vector_files) * self.cfg.test_split)
        n_train = len(matched_vector_files) - n_val - n_test
        splits = {
            "train": matched_vector_files[:n_train],
            "validation": matched_vector_files[n_train:n_train + n_val],
            "test": matched_vector_files[n_train + n_val:]
        }
        self.split_manifest = self._build_split_manifest(splits, raster_map)
        
        stats_cache = {}
        with ProcessPoolExecutor(self.cfg.max_workers) as executor:
            future_map = {
                executor.submit(get_stats_for_single_file, raster_map[vf.stem]): vf
                for s in splits.values()
                for vf in s
                if vf.stem in raster_map
            }
            for future in tqdm(as_completed(future_map), total=len(future_map), desc="Calculando estadísticas de imagen"):
                stats_cache[future_map[future].stem] = future.result()

        tasks = [
            (
                raster_map[vf.stem],
                vf,
                self.cfg.output_dir / 'images' / split,
                self.cfg.output_dir / 'labels' / split,
                self.cfg,
                label_col,
                self.class_map,
                stats_cache[vf.stem],
            )
            for split, files in splits.items()
            for vf in files
            if vf.stem in raster_map and vf.stem in stats_cache
        ]

        self.log.info(f"Iniciando procesamiento de {len(tasks)} tareas...")
        with ProcessPoolExecutor(max_workers=self.cfg.max_workers) as executor:
            for result in tqdm(executor.map(process_parcel_to_patches, tasks), total=len(tasks), desc="Generando parches"):
                self._merge_stats(result)
        self._save_report()
        self._save_dataset_yaml()
        self._save_split_manifest()

    def _merge_stats(self, p_stats):
        self.stats.total_patches += p_stats.get('patches', 0)
        self.stats.total_objects += p_stats.get('objects', 0)
        self.stats.errors += p_stats.get('errors', 0)
        self.stats.parcels_processed += 1
        for cls, count in p_stats.get('objects_per_class', {}).items():
            self.stats.objects_per_class[cls] = self.stats.objects_per_class.get(cls, 0) + count

    def _save_report(self):
        report = self.stats.to_dict()
        report['class_map'] = self.class_map
        report['label_column'] = self.label_column
        report['config'] = _json_safe_config(self.cfg)
        report['split_counts'] = {split: len(items) for split, items in self.split_manifest.get("splits", {}).items()}
        report['unmatched_vectors'] = self.unmatched_vectors
        report['unmatched_rasters'] = self.unmatched_rasters
        report_path = self.cfg.output_dir / 'patcher_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        self.log.info(f"Proceso completado. Reporte guardado en: {report_path}")

    def _build_split_manifest(self, splits, raster_map):
        return {
            "created_at": datetime.now().isoformat(),
            "random_seed": self.cfg.random_seed,
            "validation_split": self.cfg.validation_split,
            "test_split": self.cfg.test_split,
            "label_column": self.label_column,
            "class_map": self.class_map,
            "splits": {
                split: [
                    {
                        "parcel_id": vf.stem,
                        "vector_file": vf.name,
                        "raster_file": raster_map[vf.stem].name,
                    }
                    for vf in files
                ]
                for split, files in splits.items()
            },
            "unmatched_vectors": self.unmatched_vectors,
            "unmatched_rasters": self.unmatched_rasters,
        }

    def _save_split_manifest(self):
        manifest_path = self.cfg.output_dir / 'split_manifest.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(self.split_manifest, f, indent=4, ensure_ascii=False)
        self.log.info(f"Manifiesto de particiones guardado en: {manifest_path}")

    def _save_dataset_yaml(self):
        names = "\n".join(
            f"  {index}: {name}"
            for name, index in sorted(self.class_map.items(), key=lambda item: item[1])
        )
        yaml_content = f"""path: {self.cfg.output_dir.resolve()}
train: images/train
val: images/validation
test: images/test

names:
{names}
"""
        yaml_path = self.cfg.output_dir / "dataset.yaml"
        with open(yaml_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        self.log.info(f"Archivo YAML guardado en: {yaml_path}")


def _json_safe_config(config: PatcherConfig) -> Dict[str, Any]:
    raw = asdict(config)
    return {key: str(value) if isinstance(value, Path) else value for key, value in raw.items()}


def clean_output_dir(output_dir: Path, ml_root: Path):
    resolved_output = output_dir.resolve()
    allowed_root = (ml_root / "data" / "datasets").resolve()
    if resolved_output == allowed_root or allowed_root not in resolved_output.parents:
        raise ValueError(
            f"--clean-output solo puede usarse dentro de {allowed_root}. "
            f"Ruta recibida: {resolved_output}"
        )
    if resolved_output.exists():
        shutil.rmtree(resolved_output)

if __name__ == "__main__":
    import argparse

    # Importar configuración desde archivo centralizado
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from configs import dataset_config as cfg

    # Argumentos CLI opcionales (para sobrescribir config)
    parser = argparse.ArgumentParser(description="Genera datasets YOLO con parches")
    parser.add_argument("--patch-size", type=int, default=None,
                        help="Tamaño de parche en píxeles (sobrescribe config)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Directorio de salida (sobrescribe config)")
    parser.add_argument("--clean-output", action="store_true",
                        help="Elimina el directorio de salida antes de generar el dataset")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else cfg.OUTPUT_DIR
    if not output_dir.is_absolute():
        output_dir = (cfg.ML_ROOT / output_dir).resolve()
    if args.clean_output:
        clean_output_dir(output_dir, cfg.ML_ROOT)

    # --- CONFIGURACIÓN DESDE ARCHIVO CENTRALIZADO ---
    config = PatcherConfig(
        raster_dir=cfg.RASTER_DIR,
        vector_dir=cfg.VECTOR_DIR,
        output_dir=output_dir,
        patch_size_pixels=args.patch_size if args.patch_size else cfg.PATCH_SIZE,
        patch_overlap=cfg.PATCH_OVERLAP,
        max_workers=cfg.MAX_WORKERS,
        validation_split=cfg.VALIDATION_SPLIT,
        test_split=cfg.TEST_SPLIT,
        random_seed=cfg.RANDOM_SEED,
        merge_overlapping_bboxes=cfg.MERGE_OVERLAPPING_BBOXES,
        bbox_enlargement_factor=cfg.BBOX_ENLARGEMENT_FACTOR,
        skip_empty_patches=cfg.SKIP_EMPTY_PATCHES,
        target_class=cfg.TARGET_CLASS,
        edge_buffer_percentage=cfg.EDGE_BUFFER_PERCENTAGE
    )

    logger = setup_logger(config.output_dir / 'logs')
    try:
        YoloPatcher(config, logger).process()
    except (KeyboardInterrupt, SystemExit):
        logger.warning("Proceso interrumpido por el usuario.")
    except Exception as e:
        logger.exception(f"Error fatal no controlado: {e}")
