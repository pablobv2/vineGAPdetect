"""Construcción de GeoPackage (.gpkg) con las detecciones georreferenciadas.

Las detecciones llegan con `obb_polygon` en coordenadas de píxel del TIFF original.
Aplicamos la transformación afín de rasterio para llevar cada vértice a coordenadas
del CRS del ortomosaico, y serializamos como capa de polígonos en un único GPKG.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

import fiona


def _apply_affine(transform: list[float], col: float, row: float) -> tuple[float, float]:
    a, b, c, d, e, f = transform
    return (a * col + b * row + c, d * col + e * row + f)


def build_detections_gpkg(
    detections: list[dict[str, Any]],
    transform: list[float] | None,
    crs: str | None,
    parcel_name: str | None = None,
    conf_threshold: float = 0.0,
) -> bytes:
    if not transform or len(transform) != 6:
        raise ValueError(
            "Falta la transformación afín del ortomosaico. "
            "Solo se puede exportar GPKG si el archivo original era un GeoTIFF georreferenciado."
        )
    if not crs:
        raise ValueError(
            "El ortomosaico no tiene un CRS asociado. No se puede exportar a GPKG."
        )

    schema = {
        "geometry": "Polygon",
        "properties": {
            "id": "int",
            "class_name": "str:64",
            "confidence": "float",
            "missing_vines": "int",
            "parcel": "str:128",
        },
    }

    with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tmp:
        path = tmp.name
    # Fiona necesita crear el fichero desde cero; borramos el vacío que creó NamedTemporaryFile
    os.unlink(path)

    try:
        written = 0
        with fiona.open(
            path,
            "w",
            driver="GPKG",
            schema=schema,
            crs=crs,
            layer="marras",
        ) as sink:
            for det in detections:
                confidence = float(det.get("confidence", 0.0))
                if confidence < conf_threshold:
                    continue
                polygon_px = det.get("obb_polygon") or []
                if len(polygon_px) < 3:
                    continue

                ring = [_apply_affine(transform, float(p[0]), float(p[1])) for p in polygon_px]
                if ring[0] != ring[-1]:
                    ring.append(ring[0])

                feature = {
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                    "properties": {
                        "id": int(det.get("id", 0)),
                        "class_name": str(det.get("class_name", "marra")),
                        "confidence": confidence,
                        "missing_vines": int(det.get("estimated_missing_vines", 0)),
                        "parcel": str(parcel_name or ""),
                    },
                }
                sink.write(feature)
                written += 1

        if written == 0:
            raise ValueError(
                "No hay detecciones por encima del umbral de confianza para exportar."
            )

        with open(path, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
