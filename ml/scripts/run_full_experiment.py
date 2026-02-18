# -*- coding: utf-8 -*-
"""
Orquesta el experimento completo reproducible para el Anexo V.

Ejecuta:
1. captura del entorno,
2. comparativa de datasets/modelos,
3. evaluacion final en test,
4. explicabilidad Eigen-CAM del mejor modelo en test.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
RESULTS_DIR = PROJECT_ROOT / "results"
TRAINING_RESULTS_DIR = RESULTS_DIR / "vineGAPdetect_Training"


def run_step(name: str, command: list[str]) -> dict[str, object]:
    print("\n" + "=" * 80)
    print(f"[{name}] {' '.join(command)}")
    print("=" * 80)
    started_at = datetime.now()
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    ended_at = datetime.now()
    result = {
        "name": name,
        "command": command,
        "returncode": completed.returncode,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": round((ended_at - started_at).total_seconds(), 2),
    }
    if completed.returncode != 0:
        raise RuntimeError(f"Fallo el paso '{name}' con codigo {completed.returncode}")
    return result


def load_best_test_experiment() -> tuple[str, str]:
    evaluation_path = RESULTS_DIR / "test_evaluation.json"
    partial_path = RESULTS_DIR / "comparison_partial.json"

    if not evaluation_path.exists():
        raise FileNotFoundError(f"No existe {evaluation_path}")
    if not partial_path.exists():
        raise FileNotFoundError(f"No existe {partial_path}")

    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    rows = evaluation.get("results", [])
    valid_rows = [row for row in rows if float(row.get("mAP@50-95", 0.0)) > 0.0]
    if not valid_rows:
        raise RuntimeError("No hay modelos con metrica mAP@50-95 valida en test_evaluation.json")

    best = max(valid_rows, key=lambda row: float(row.get("mAP@50-95", 0.0)))
    experiment_name = str(best["Experimento"])

    comparison = json.loads(partial_path.read_text(encoding="utf-8"))
    for item in comparison:
        if item.get("name") == experiment_name and item.get("config"):
            return experiment_name, str(item["config"]["dataset_dir"])

    raise RuntimeError(f"No se encontro el dataset asociado a {experiment_name} en comparison_partial.json")


def write_manifest(steps: list[dict[str, object]], best_experiment: str | None, dataset_dir: str | None) -> None:
    manifest = {
        "created_at": datetime.now().isoformat(),
        "steps": steps,
        "best_experiment": best_experiment,
        "best_dataset_dir": dataset_dir,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "full_experiment_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta el experimento completo del Anexo V")
    parser.add_argument("--skip-xai", action="store_true", help="No genera Eigen-CAM al finalizar")
    parser.add_argument("--xai-method", choices=["eigencam", "gradcam"], default="eigencam")
    parser.add_argument("--xai-imgsz", type=int, default=640)
    args = parser.parse_args()

    steps: list[dict[str, object]] = []
    best_experiment = None
    dataset_dir = None

    try:
        steps.append(run_step("environment", [sys.executable, str(SCRIPTS_DIR / "capture_environment.py")]))
        steps.append(run_step("comparison", [sys.executable, str(SCRIPTS_DIR / "compare_models.py"), "--yes"]))
        steps.append(run_step("test_evaluation", [sys.executable, str(SCRIPTS_DIR / "evaluate_on_test.py")]))

        best_experiment, dataset_dir = load_best_test_experiment()
        if not args.skip_xai:
            model_path = TRAINING_RESULTS_DIR / best_experiment / "weights" / "best.pt"
            image_dir = PROJECT_ROOT / dataset_dir / "images" / "test"
            output_dir = RESULTS_DIR / "Explainability" / best_experiment
            steps.append(
                run_step(
                    "explainability",
                    [
                        sys.executable,
                        str(SCRIPTS_DIR / "explainability_cam.py"),
                        "--model",
                        str(model_path),
                        "--image",
                        str(image_dir),
                        "--output-dir",
                        str(output_dir),
                        "--method",
                        args.xai_method,
                        "--imgsz",
                        str(args.xai_imgsz),
                    ],
                )
            )
    finally:
        write_manifest(steps, best_experiment, dataset_dir)

    print("\nExperimento completo finalizado.")
    print(f"Mejor experimento: {best_experiment}")
    print(f"Manifiesto: {(RESULTS_DIR / 'full_experiment_manifest.json').resolve()}")


if __name__ == "__main__":
    main()
