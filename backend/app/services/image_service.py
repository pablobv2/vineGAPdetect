from __future__ import annotations

import base64
import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from rasterio.io import MemoryFile
from rasterio.windows import Window
from rasterio.warp import transform


@dataclass
class LoadedImage:
    """Imagen RGB normalizada junto con metadatos raster y geoespaciales extraidos.

    Es el contrato interno que permite tratar de forma homogenea imagenes
    convencionales y ortomosaicos GeoTIFF. Incluye dimensiones, resolucion,
    unidad, CRS, transformacion afin, area aproximada, centro geografico y fecha
    de adquisicion cuando esa informacion esta disponible en el raster.
    """
    image_rgb: np.ndarray
    file_type: str
    resolution_x: float
    resolution_y: float
    resolution_unit: str | None = None
    crs: str | None = None
    # Affine transform from pixel coordinates to CRS: a, b, c, d, e, f.
    # X = a*col + b*row + c; Y = d*col + e*row + f.
    transform: list[float] | None = None
    parcel_area_hectares: float | None = None
    location_center_lat: float | None = None
    location_center_lon: float | None = None
    acquisition_date: str | None = None


def is_geotiff_filename(filename: str) -> bool:
    lower = filename.lower()
    return lower.endswith(".tif") or lower.endswith(".tiff")


def _detect_iso_image_format(content: bytes) -> str | None:
    if len(content) < 12 or content[4:8] != b"ftyp":
        return None

    brands = {content[8:12], *[content[i:i + 4] for i in range(16, min(len(content), 64), 4)]}
    if brands.intersection({b"avif", b"avis"}):
        return "AVIF"
    if brands.intersection({b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}):
        return "HEIF/HEIC"
    return None


def _normalize_band_to_uint8(band: np.ndarray) -> np.ndarray:
    valid = band[band > 0]
    if valid.size == 0:
        valid = band
    if valid.size == 0:
        return np.zeros_like(band, dtype=np.uint8)

    min_val, max_val = np.percentile(valid, (2, 98))
    if max_val <= min_val:
        return np.zeros_like(band, dtype=np.uint8)

    normalized = np.clip((band.astype(np.float32) - min_val) / (max_val - min_val + 1e-6), 0.0, 1.0)
    return (normalized * 255.0).astype(np.uint8)


def _extract_acquisition_date(tags: dict[str, str]) -> str | None:
    for key in (
        "TIFFTAG_DATETIME",
        "DATETIME",
        "DATE_ACQUIRED",
        "ACQUISITION_DATE",
        "ACQ_DATE",
        "capture_date",
        "CaptureDate",
    ):
        value = tags.get(key)
        if value:
            return str(value)
    return None


def _normalize_unit_name(raw_unit: str | None) -> str:
    if not raw_unit:
        return "m"
    unit = raw_unit.strip().lower()
    if unit in {"metre", "meter", "meters", "metres"}:
        return "m"
    if unit in {"foot", "feet", "ft", "us survey foot"}:
        return "ft"
    return raw_unit


def _linear_unit_info(crs) -> tuple[str, float]:
    unit_name = _normalize_unit_name(getattr(crs, "linear_units", None))
    meters_factor = 1.0

    factor_info = getattr(crs, "linear_units_factor", None)
    if isinstance(factor_info, tuple) and len(factor_info) >= 2:
        try:
            unit_name = _normalize_unit_name(str(factor_info[0]))
            meters_factor = float(factor_info[1])
        except Exception:
            meters_factor = 1.0
    elif isinstance(factor_info, (int, float)):
        meters_factor = float(factor_info)

    if not np.isfinite(meters_factor) or meters_factor <= 0:
        meters_factor = 1.0
    return unit_name, meters_factor


def _to_wgs84_center(crs, center_x: float, center_y: float) -> tuple[float | None, float | None]:
    if crs is None:
        return None, None
    try:
        longitudes, latitudes = transform(crs, "EPSG:4326", [center_x], [center_y])
        if len(longitudes) == 1 and len(latitudes) == 1:
            lon = float(longitudes[0])
            lat = float(latitudes[0])
            if np.isfinite(lon) and np.isfinite(lat):
                return lat, lon
    except Exception:
        pass
    return None, None


def load_geotiff_from_bytes(content: bytes) -> LoadedImage:
    """Lee un GeoTIFF desde memoria y extrae imagen RGB, resolucion, CRS y metadatos de parcela.

    Normaliza bandas raster a 8 bits para visualizacion e inferencia, conserva
    la transformacion pixel-CRS necesaria para exportar resultados y calcula
    metadatos agronomicos basicos como area aproximada y centro geografico.
    """
    with MemoryFile(content) as memfile:
        with memfile.open() as src:
            data = src.read(list(range(1, min(src.count, 3) + 1)))
            channels, height, width = data.shape

            image = np.zeros((height, width, 3), dtype=np.uint8)
            for i in range(min(channels, 3)):
                image[:, :, i] = _normalize_band_to_uint8(data[i])

            if channels == 1:
                image[:, :, 1] = image[:, :, 0]
                image[:, :, 2] = image[:, :, 0]

            res_x, res_y = src.res
            crs_value = src.crs.to_string() if src.crs else None
            affine = src.transform
            transform_list = [
                float(affine.a), float(affine.b), float(affine.c),
                float(affine.d), float(affine.e), float(affine.f),
            ] if affine is not None else None
            acquisition_date = _extract_acquisition_date(src.tags())

            resolution_unit: str | None = None
            parcel_area_hectares: float | None = None
            if src.crs:
                if src.crs.is_projected:
                    unit_name, meter_factor = _linear_unit_info(src.crs)
                    resolution_unit = unit_name
                    pixel_width_m = abs(float(res_x)) * meter_factor
                    pixel_height_m = abs(float(res_y)) * meter_factor
                    area_m2 = float(width * height) * pixel_width_m * pixel_height_m
                    if area_m2 > 0:
                        parcel_area_hectares = area_m2 / 10000.0
                elif src.crs.is_geographic:
                    resolution_unit = "deg"

            bounds = src.bounds
            center_x = (float(bounds.left) + float(bounds.right)) / 2.0
            center_y = (float(bounds.bottom) + float(bounds.top)) / 2.0
            center_lat, center_lon = _to_wgs84_center(src.crs, center_x, center_y)

            return LoadedImage(
                image_rgb=image,
                file_type="geotiff",
                resolution_x=float(res_x),
                resolution_y=float(res_y),
                resolution_unit=resolution_unit,
                crs=crs_value,
                transform=transform_list,
                parcel_area_hectares=parcel_area_hectares,
                location_center_lat=center_lat,
                location_center_lon=center_lon,
                acquisition_date=acquisition_date,
            )


def extract_geotiff_patch_from_bytes(content: bytes, x_off: int, y_off: int, patch_size: int) -> np.ndarray:
    """Extrae una ventana RGB de tamano fijo desde un GeoTIFF sin cargar todo el raster.

    Se usa en XAI para trabajar solo sobre el parche analizado, reduciendo
    memoria y manteniendo coherencia con imagenes geoespaciales grandes.
    """
    with MemoryFile(content) as memfile:
        with memfile.open() as src:
            channels = min(src.count, 3)
            patch = np.zeros((patch_size, patch_size, 3), dtype=np.uint8)

            read_width = max(0, min(patch_size, src.width - x_off))
            read_height = max(0, min(patch_size, src.height - y_off))
            if read_width == 0 or read_height == 0:
                return patch

            window = Window(x_off, y_off, read_width, read_height)
            data = src.read(list(range(1, channels + 1)), window=window)

            for i in range(channels):
                patch[:read_height, :read_width, i] = _normalize_band_to_uint8(data[i])

            if channels == 1:
                patch[:, :, 1] = patch[:, :, 0]
                patch[:, :, 2] = patch[:, :, 0]

            return patch


def load_regular_image_from_bytes(content: bytes) -> LoadedImage:
    """Carga una imagen convencional con Pillow y asigna resolucion de pixel no georreferenciada."""
    unsupported_format = _detect_iso_image_format(content)
    if unsupported_format:
        raise ValueError(
            f"Formato {unsupported_format} no soportado para inferencia. "
            "Formato no soportado para inferencia. Se requiere un archivo JPEG o PNG real; cambiar la extension no modifica el formato interno."
        )

    try:
        image = Image.open(io.BytesIO(content)).convert("RGB")
    except ModuleNotFoundError as exc:
        if exc.name == "pi_heif":
            raise ValueError(
                "La imagen parece estar en formato HEIF/AVIF y requiere una dependencia no disponible en el backend. "
                "Se requiere convertir la imagen a JPEG o PNG real antes de la carga."
            ) from exc
        raise
    except UnidentifiedImageError as exc:
        raise ValueError(
            "No se pudo leer la imagen. El archivo debe ser JPEG, PNG o GeoTIFF valido y la extension debe coincidir con el formato real."
        ) from exc

    arr = np.array(image)
    return LoadedImage(
        image_rgb=arr,
        file_type="image",
        resolution_x=1.0,
        resolution_y=1.0,
        resolution_unit="px",
    )


def load_image_from_upload(content: bytes, filename: str) -> LoadedImage:
    """Selecciona el cargador adecuado segun extension GeoTIFF o formato de imagen estandar."""
    if is_geotiff_filename(filename):
        return load_geotiff_from_bytes(content)
    return load_regular_image_from_bytes(content)


def encode_png_base64(image_rgb: np.ndarray) -> str:
    """Codifica una imagen RGB como PNG base64 para respuestas JSON."""
    image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    ok, buffer = cv2.imencode(".png", image_bgr)
    if not ok:
        raise RuntimeError("No se pudo codificar la imagen en PNG.")
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def encode_preview_jpeg(image_rgb: np.ndarray, max_side: int = 800, quality: int = 75) -> str:
    """Genera una previsualizacion JPEG reducida y codificada en base64."""
    small = resize_for_preview(image_rgb, max_side=max_side)
    pil_img = Image.fromarray(small)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def resize_for_preview(image_rgb: np.ndarray, max_side: int = 1920) -> np.ndarray:
    """Reduce una imagen manteniendo proporcion para uso interactivo en el frontend."""
    height, width = image_rgb.shape[:2]
    longest = max(width, height)
    if longest <= max_side:
        return image_rgb

    scale = max_side / float(longest)
    target_width = max(1, int(round(width * scale)))
    target_height = max(1, int(round(height * scale)))
    return cv2.resize(image_rgb, (target_width, target_height), interpolation=cv2.INTER_AREA)
