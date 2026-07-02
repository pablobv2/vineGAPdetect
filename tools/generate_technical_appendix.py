#!/usr/bin/env python3
"""Build the technical appendix from code documentation."""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "generated"
MAIN_TEX = OUT_DIR / "anexo_tecnico.tex"
PDF = OUT_DIR / "anexo_tecnico.pdf"

BACKEND_ROUTE_PREFIXES = {
    "health.py": "",
    "auth.py": "/auth",
    "users.py": "/users",
    "model.py": "/model",
    "preview.py": "/preview",
    "jobs.py": "/jobs",
    "exports.py": "/export",
    "history.py": "/history",
}

BACKEND_OVERVIEW_FILES = [
    ROOT / "backend" / "app" / "main.py",
]

BACKEND_SERVICE_FILES = [
    ROOT / "backend" / "app" / "core" / "config.py",
    ROOT / "backend" / "app" / "services" / "auth_service.py",
    ROOT / "backend" / "app" / "services" / "gpkg_export.py",
    ROOT / "backend" / "app" / "services" / "image_service.py",
    ROOT / "backend" / "app" / "services" / "inference_service.py",
    ROOT / "backend" / "app" / "services" / "job_manager.py",
    ROOT / "backend" / "app" / "services" / "model_registry.py",
    ROOT / "backend" / "app" / "services" / "user_service.py",
    ROOT / "backend" / "app" / "services" / "xai_service.py",
]

FRONTEND_DOC_FILES = [
    ROOT / "frontend" / "src" / "app" / "App.tsx",
    ROOT / "frontend" / "src" / "app" / "auth" / "AuthContext.tsx",
    ROOT / "frontend" / "src" / "app" / "api" / "client.ts",
    ROOT / "frontend" / "src" / "app" / "hooks" / "DashboardStateContext.tsx",
    ROOT / "frontend" / "src" / "app" / "hooks" / "useDashboardState.ts",
    ROOT / "frontend" / "src" / "app" / "hooks" / "useJobPolling.ts",
    ROOT / "frontend" / "src" / "app" / "components" / "Dashboard.tsx",
    ROOT / "frontend" / "src" / "app" / "components" / "InferenceCanvas.tsx",
    ROOT / "frontend" / "src" / "app" / "components" / "HistoryPage.tsx",
    ROOT / "frontend" / "src" / "app" / "components" / "ProtectedDashboard.tsx",
    ROOT / "frontend" / "src" / "app" / "components" / "admin" / "UsersPage.tsx",
    ROOT / "frontend" / "src" / "app" / "components" / "admin" / "UserCreatePage.tsx",
    ROOT / "frontend" / "src" / "app" / "utils" / "exportPdf.ts",
]

ML_DOC_FILES = [
    ROOT / "ml" / "configs" / "dataset_config.py",
    ROOT / "ml" / "scripts" / "generar_parches.py",
    ROOT / "ml" / "scripts" / "train.py",
    ROOT / "ml" / "scripts" / "compare_models.py",
    ROOT / "ml" / "scripts" / "evaluate_on_test.py",
    ROOT / "ml" / "scripts" / "explainability_cam.py",
    ROOT / "ml" / "scripts" / "yolo_cam" / "base_cam.py",
    ROOT / "ml" / "scripts" / "yolo_cam" / "eigen_cam.py",
    ROOT / "ml" / "scripts" / "yolo_cam" / "grad_cam.py",
    ROOT / "ml" / "scripts" / "yolo_cam" / "activations_and_gradients.py",
]


@dataclass(frozen=True)
class RouteDoc:
    method: str
    path: str
    handler: str
    auth: str
    response: str
    doc: str


@dataclass(frozen=True)
class SymbolDoc:
    file: str
    name: str
    kind: str
    doc: str


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def clean_doc(doc: str | None) -> str:
    if not doc:
        return ""
    doc = re.sub(r"\s+", " ", doc.strip())
    return doc


def tex_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def tex_table(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    header_list = list(headers)
    width = 0.92 / max(len(header_list), 1)
    spec = "".join(f"p{{{width:.2f}\\linewidth}}" for _ in header_list)
    lines = [
        r"\begin{longtable}{" + spec + "}",
        " & ".join(r"\textbf{" + tex_escape(h) + "}" for h in header_list) + r" \\",
        r"\hline",
        r"\endfirsthead",
        " & ".join(r"\textbf{" + tex_escape(h) + "}" for h in header_list) + r" \\",
        r"\hline",
        r"\endhead",
    ]
    for row in rows:
        lines.append(" & ".join(tex_escape(cell) for cell in row) + r" \\")
    lines.append(r"\end{longtable}")
    return "\n".join(lines)


def tex_code(value: object) -> str:
    return r"\texttt{" + tex_escape(value) + "}"


def paragraph(text: str) -> str:
    return tex_escape(text or "-") + "\n\n"


def compact_list(rows: Iterable[tuple[object, object]]) -> str:
    lines = [r"\begin{description}[leftmargin=2.8cm,style=nextline]"]
    for key, value in rows:
        lines.append(r"\item[" + tex_escape(key) + "] " + tex_escape(value))
    lines.append(r"\end{description}")
    return "\n".join(lines)


def item_list(items: Iterable[object]) -> str:
    lines = [r"\begin{itemize}[leftmargin=1.2cm,itemsep=0.15em]"]
    for item in items:
        lines.append(r"\item " + tex_escape(item))
    lines.append(r"\end{itemize}")
    return "\n".join(lines)


def symbol_blocks(symbols: list[SymbolDoc]) -> str:
    lines: list[str] = []
    for item in symbols:
        title = f"{item.name} ({item.kind})"
        lines.extend(
            [
                r"\subsubsection*{" + tex_escape(title) + "}",
                r"\noindent\textbf{Fichero:} " + tex_code(item.file) + r"\\",
                paragraph(item.doc),
            ]
        )
    return "\n".join(lines) if lines else paragraph("No hay documentacion extraible.")


def route_blocks(routes: list[RouteDoc]) -> str:
    lines: list[str] = []
    for route in routes:
        title = f"{route.method} {route.path}"
        lines.extend(
            [
                r"\subsubsection*{" + tex_escape(title) + "}",
                compact_list(
                    [
                        ("Handler", route.handler),
                        ("Acceso", route.auth),
                        ("Respuesta", route.response),
                    ]
                ),
                paragraph(route.doc or "Ruta sin docstring tecnico."),
            ]
        )
    return "\n".join(lines)


def dependency_blocks(rows: list[tuple[str, str, str]]) -> str:
    grouped: dict[str, list[tuple[str, str]]] = {}
    for scope, name, version in rows:
        grouped.setdefault(scope, []).append((name, version))

    lines: list[str] = []
    for scope in sorted(grouped):
        lines.append(r"\subsection*{" + tex_escape(scope) + "}")
        lines.append(compact_list((name, version) for name, version in grouped[scope]))
    return "\n".join(lines)


def docker_compose_blocks() -> str:
    path = ROOT / "docker-compose.yml"
    if not path.exists():
        return paragraph("No se ha encontrado docker-compose.yml.")

    source = read_text(path).splitlines()
    services: dict[str, list[str]] = {}
    current: str | None = None
    for line in source:
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            current = match.group(1)
            services[current] = []
            continue
        if current and (line.startswith("    ") or not line.strip()):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                services[current].append(stripped)

    lines: list[str] = []
    for service, block in services.items():
        selected = [
            item
            for item in block
            if item.startswith(("build:", "dockerfile:", "ports:", "depends_on:", "environment:", "volumes:", "restart:", "healthcheck:", "-", "DEVICE:", "FRONTEND_ORIGIN:"))
        ]
        lines.extend(
            [
                r"\subsubsection*{" + tex_escape(service) + "}",
                item_list(selected),
            ]
        )
    return "\n".join(lines) if lines else paragraph("docker-compose.yml no contiene servicios extraibles.")


def normalize_route(prefix: str, route_path: str) -> str:
    if route_path == "/":
        route_path = ""
    return re.sub(r"//+", "/", f"/api/v1{prefix}{route_path}")


def route_method(decorator: ast.AST) -> str | None:
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    if isinstance(decorator, ast.Attribute) and isinstance(decorator.value, ast.Name):
        if decorator.value.id == "router" and decorator.attr in {"get", "post", "patch", "delete"}:
            return decorator.attr.upper()
    return None


def first_route_arg(decorator: ast.Call) -> str:
    if decorator.args and isinstance(decorator.args[0], ast.Constant):
        value = decorator.args[0].value
        if isinstance(value, str):
            return value
    return ""


def response_model(decorator: ast.Call) -> str:
    for keyword in decorator.keywords:
        if keyword.arg == "response_model":
            return ast.unparse(keyword.value)
    return "-"


def infer_auth(source: str) -> str:
    if "require_admin" in source:
        return "administrador"
    if "require_operator_or_admin" in source:
        return "operador/administrador"
    if "get_current_user" in source:
        return "usuario autenticado"
    return "publico"


def backend_routes() -> list[RouteDoc]:
    docs: list[RouteDoc] = []
    for path in sorted((ROOT / "backend" / "app" / "api" / "routes").glob("*.py")):
        prefix = BACKEND_ROUTE_PREFIXES.get(path.name)
        if prefix is None:
            continue
        source = read_text(path)
        tree = ast.parse(source)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            node_source = ast.get_source_segment(source, node) or ""
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                method = route_method(decorator)
                if method is None:
                    continue
                route_source = ast.get_source_segment(source, decorator) or ""
                docs.append(
                    RouteDoc(
                        method=method,
                        path=normalize_route(prefix, first_route_arg(decorator)),
                        handler=node.name,
                        auth=infer_auth(route_source + "\n" + node_source),
                        response=response_model(decorator),
                        doc=clean_doc(ast.get_docstring(node)),
                    )
                )
    return sorted(docs, key=lambda item: (item.path, item.method))


def python_symbol_docs(paths: Iterable[Path], include_functions: bool = True) -> list[SymbolDoc]:
    docs: list[SymbolDoc] = []
    for path in paths:
        if not path.exists():
            continue
        tree = ast.parse(read_text(path))
        module_doc = clean_doc(ast.get_docstring(tree))
        if module_doc:
            docs.append(SymbolDoc(rel(path), rel(path), "module", module_doc))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                doc = clean_doc(ast.get_docstring(node))
                if doc:
                    docs.append(SymbolDoc(rel(path), node.name, "class", doc))
            elif include_functions and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                doc = clean_doc(ast.get_docstring(node))
                if doc:
                    docs.append(SymbolDoc(rel(path), node.name, "function", doc))
    return docs


def frontend_routes() -> list[tuple[str, str]]:
    routes_path = ROOT / "frontend" / "src" / "app" / "routes.ts"
    source = read_text(routes_path)
    pattern = re.compile(r"path:\s*['\"]([^'\"]+)['\"],\s*Component:\s*([A-Za-z0-9_]+)", re.MULTILINE)
    return pattern.findall(source)


def clean_jsdoc(block: str) -> str:
    lines = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^/\*\*", "", line)
        line = re.sub(r"\*/$", "", line)
        line = re.sub(r"^\*", "", line).strip()
        if line and not line.startswith("@"):
            lines.append(line)
    return clean_doc(" ".join(lines))


def frontend_symbol_docs(paths: Iterable[Path]) -> list[SymbolDoc]:
    docs: list[SymbolDoc] = []
    pattern = re.compile(
        r"/\*\*(?P<doc>(?:(?!\*/).)*?)\*/\s*export\s+"
        r"(?:(?P<kind>async\s+function|function|const|class|interface|type)\s+)?"
        r"(?P<name>[A-Za-z0-9_]+)",
        re.DOTALL,
    )
    for path in paths:
        if not path.exists():
            continue
        for match in pattern.finditer(read_text(path)):
            kind = (match.group("kind") or "symbol").replace("async ", "")
            docs.append(SymbolDoc(rel(path), match.group("name"), kind, clean_jsdoc(match.group("doc"))))
    return [item for item in docs if item.doc]


def dependency_rows() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    package_path = ROOT / "frontend" / "package.json"
    if package_path.exists():
        package = json.loads(read_text(package_path))
        for section in ("dependencies", "devDependencies"):
            for name, version in sorted(package.get(section, {}).items()):
                rows.append(("frontend", name, version))
    for scope, path in (
        ("backend", ROOT / "backend" / "requirements.txt"),
        ("ml", ROOT / "ml" / "requirements.txt"),
    ):
        if not path.exists():
            continue
        for line in read_text(path).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"([A-Za-z0-9_.-]+)(.*)", line)
            if match:
                rows.append((scope, match.group(1), match.group(2).strip() or "-"))
    return rows


def section(title: str, content: str) -> str:
    return "\n".join([r"\chapter{" + tex_escape(title) + "}", content, ""])


def subsection(title: str, content: str) -> str:
    return "\n".join([r"\section{" + tex_escape(title) + "}", content, ""])


def symbol_table(symbols: list[SymbolDoc]) -> str:
    return tex_table(
        ["Fichero", "Simbolo", "Tipo", "Documentacion extraida"],
        ((item.file, item.name, item.kind, item.doc) for item in symbols),
    )


def write_partials() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    backend = "\n".join(
        [
            section("Backend", ""),
            subsection("Arranque y composición", symbol_blocks(python_symbol_docs(BACKEND_OVERVIEW_FILES, include_functions=False))),
            subsection("Endpoints FastAPI", route_blocks(backend_routes())),
            subsection("Servicios internos", symbol_blocks(python_symbol_docs(BACKEND_SERVICE_FILES))),
        ]
    )
    (OUT_DIR / "backend.tex").write_text(backend, encoding="utf-8")

    frontend = "\n".join(
        [
            section("Frontend", ""),
            subsection("Rutas React", compact_list(frontend_routes())),
            subsection("Componentes y módulos documentados", symbol_blocks(frontend_symbol_docs(FRONTEND_DOC_FILES))),
        ]
    )
    (OUT_DIR / "frontend.tex").write_text(frontend, encoding="utf-8")

    ml = "\n".join(
        [
            section("Módulo ML", ""),
            subsection("Pipeline experimental y librería de explicabilidad", symbol_blocks(python_symbol_docs(ML_DOC_FILES, include_functions=False))),
        ]
    )
    (OUT_DIR / "ml.tex").write_text(ml, encoding="utf-8")


def write_main_tex() -> None:
    MAIN_TEX.write_text(
        "\n".join(
            [
                r"\documentclass[11pt,a4paper]{report}",
                r"\usepackage[margin=2.5cm]{geometry}",
                r"\usepackage{fontspec}",
                r"\usepackage{longtable}",
                r"\usepackage{array}",
                r"\usepackage{enumitem}",
                r"\usepackage{hyperref}",
                r"\usepackage{titlesec}",
                r"\setmainfont{Latin Modern Roman}",
                r"\renewcommand{\contentsname}{Índice}",
                r"\renewcommand{\chaptername}{Capítulo}",
                r"\sloppy",
                r"\emergencystretch=4em",
                r"\setlength{\LTpre}{0.6em}",
                r"\setlength{\LTpost}{1em}",
                r"\title{Anexo técnico}",
                r"\author{vineGAPdetect}",
                r"\date{}",
                r"\begin{document}",
                r"\maketitle",
                r"\tableofcontents",
                r"\newpage",
                r"\input{frontend.tex}",
                r"\input{backend.tex}",
                r"\input{ml.tex}",
                r"\end{document}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_pdf() -> None:
    engine = shutil.which("xelatex") or shutil.which("pdflatex")
    if engine is None:
        raise RuntimeError("No LaTeX engine found. Install xelatex or pdflatex.")
    for _ in range(2):
        subprocess.run(
            [
                engine,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory",
                str(OUT_DIR),
                str(MAIN_TEX),
            ],
            cwd=OUT_DIR,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-pdf", action="store_true", help="Only generate LaTeX files.")
    args = parser.parse_args()

    write_partials()
    write_main_tex()
    if not args.no_pdf:
        build_pdf()

    print(f"Generated {rel(MAIN_TEX)}")
    if PDF.exists():
        print(f"Generated {rel(PDF)}")


if __name__ == "__main__":
    main()
