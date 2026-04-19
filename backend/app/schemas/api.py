from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobType(str, Enum):
    inference = "inference"
    xai = "xai"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    device: str
    model_loaded: bool
    yolo_cam_available: bool
    model_path: str


class ModelInfoResponse(BaseModel):
    task: str = "obb"
    model_path: str
    device: str
    xai_methods: list[str]
    default_slice_size: int
    max_upload_mb: int


class PreviewImageResponse(BaseModel):
    file_type: str
    source_width: int
    source_height: int
    preview_width: int
    preview_height: int
    resolution_x: float = 1.0
    resolution_y: float = 1.0
    resolution_unit: str | None = None
    crs: str | None = None
    parcel_area_hectares: float | None = None
    location_center_lat: float | None = None
    location_center_lon: float | None = None
    acquisition_date: str | None = None
    preview_png_base64: str


class DetectionItem(BaseModel):
    id: int
    class_name: str
    confidence: float
    bbox_xyxy: list[int] = Field(min_length=4, max_length=4)
    obb_polygon: list[list[float]] | None = None
    estimated_missing_vines: int = 1


class ImageMeta(BaseModel):
    width: int
    height: int
    file_type: str
    resolution_x: float = 1.0
    resolution_y: float = 1.0
    resolution_unit: str | None = None
    crs: str | None = None
    transform: list[float] | None = Field(default=None, min_length=6, max_length=6)
    parcel_area_hectares: float | None = None
    location_center_lat: float | None = None
    location_center_lon: float | None = None
    acquisition_date: str | None = None
    has_source_artifact: bool = False


class ExportDetectionItem(BaseModel):
    id: int
    class_name: str = "marra"
    confidence: float
    obb_polygon: list[list[float]] = Field(min_length=3)
    estimated_missing_vines: int = 0


class ExportDetectionsRequest(BaseModel):
    detections: list[ExportDetectionItem]
    transform: list[float] = Field(min_length=6, max_length=6)
    crs: str
    parcel_name: str | None = None
    conf_threshold: float = 0.0


class InferenceSummary(BaseModel):
    detections_count: int
    confidence_mean: float
    estimated_missing_vines_total: int
    processing_time_seconds: float


class InferenceResult(BaseModel):
    image_meta: ImageMeta
    summary: InferenceSummary
    detections: list[DetectionItem]


class XAIResult(BaseModel):
    requested_method: str | None = None
    method: str
    xai_scope: str | None = None
    width: int
    height: int
    overlay_png_base64: str
    combined_png_base64: str
    has_detections: bool | None = None
    used_conf_threshold: float | None = None
    used_target_layers: list[int] | None = None
    fallback_reason: str | None = None
    fallback_details: str | None = None


class JobAcceptedResponse(BaseModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    created_at: datetime


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None
    result: dict[str, Any] | None = None


class DeleteJobResponse(BaseModel):
    deleted: bool


class AnalysisHistoryItem(BaseModel):
    id: int
    user_id: str | None
    username: str | None
    filename: str
    original_filename: str | None = None
    executed_at: datetime
    detection_count: int
    all_detection_count: int = 0
    mean_confidence: float | None
    estimated_missing: int
    processing_time_s: float | None
    display_confidence_threshold: float | None = None
    capture_confidence_threshold: float | None = None
    typical_vine_width: float | None = None
    slice_size: int | None = None
    overlap_ratio: float | None = None
    model_path: str | None = None
    source_width: int | None = None
    source_height: int | None = None
    file_type: str | None = None
    resolution_x: float | None = None
    resolution_y: float | None = None
    resolution_unit: str | None = None
    crs: str | None = None
    transform: list[float] | None = None
    parcel_area_hectares: float | None = None
    location_center_lat: float | None = None
    location_center_lon: float | None = None
    acquisition_date: str | None = None
    has_source_artifact: bool = False
    saved: bool = False
    source_file_size_bytes: int | None = None


class AnalysisHistoryDetail(AnalysisHistoryItem):
    preview_png_b64: str | None
    result_json: str | None


class QuotaResponse(BaseModel):
    used_bytes: int
    total_bytes: int


class SaveParcelResponse(BaseModel):
    saved: bool
    used_bytes: int
    total_bytes: int
