# -*- coding: utf-8 -*-
"""
Guarda evidencias del entorno experimental en ml/results/environment.

Ejecutalo en el mismo equipo en el que se entrenan/evaluan los modelos.
"""

import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "results" / "environment"


def run_command(command: list[str]) -> dict[str, str | int]:
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "command": " ".join(command),
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except FileNotFoundError as exc:
        return {
            "command": " ".join(command),
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
        }


def write_text(name: str, content: str) -> None:
    (OUTPUT_DIR / name).write_text(content + ("\n" if content else ""), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    commands = {
        "pip_freeze": [sys.executable, "-m", "pip", "freeze"],
        "git_commit": ["git", "rev-parse", "HEAD"],
        "git_status": ["git", "status", "--short"],
        "nvidia_smi": ["nvidia-smi"],
    }
    command_results = {name: run_command(command) for name, command in commands.items()}

    write_text("python_version.txt", sys.version)
    write_text("platform.txt", platform.platform())
    for name, result in command_results.items():
        write_text(f"{name}.txt", str(result["stdout"]))
        if result["stderr"]:
            write_text(f"{name}_stderr.txt", str(result["stderr"]))

    summary = {
        "created_at": datetime.now().isoformat(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "commands": command_results,
    }
    (OUTPUT_DIR / "environment_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Entorno guardado en: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
