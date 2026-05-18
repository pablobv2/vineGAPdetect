export type JobType = "inference" | "xai";
export type JobStatus = "queued" | "running" | "completed" | "failed";
export type UserRole = "admin" | "operator";

export interface UserPublic {
  id: string;
  username: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
}
export interface LoginPayload { username: string; password: string; }
export interface AuthSession { access_token: string; token_type: string; expires_at: string; user: UserPublic; }
export interface CreateUserPayload { username: string; full_name: string; password: string; role: UserRole; is_active: boolean; }
export interface UpdateUserPayload { full_name?: string; role?: UserRole; is_active?: boolean; }

export interface DetectionItem {
  id: number;
  class_name: string;
  confidence: number;
  bbox_xyxy: [number, number, number, number];
  obb_polygon?: [number, number][];
  estimated_missing_vines: number;
}
export interface ImageMeta {
  width: number;
  height: number;
  file_type: string;
  resolution_x: number;
  resolution_y: number;
  resolution_unit?: string | null;
  crs?: string | null;
  /** Affine transform píxel→CRS: [a, b, c, d, e, f] */
  transform?: number[] | null;
  parcel_area_hectares?: number | null;
  location_center_lat?: number | null;
  location_center_lon?: number | null;
  acquisition_date?: string | null;
}
export interface InferenceSummary { detections_count: number; confidence_mean: number; estimated_missing_vines_total: number; processing_time_seconds: number; }
export interface InferenceParameters {
  capture_confidence_threshold?: number;
  display_confidence_threshold?: number;
  typical_vine_width?: number;
  slice_size?: number;
  overlap_ratio?: number;
  model_path?: string;
}
export interface InferenceResult {
  image_meta: ImageMeta;
  parameters?: InferenceParameters;
  summary: InferenceSummary;
  summary_all?: InferenceSummary;
  summary_display?: InferenceSummary;
  detections: DetectionItem[];
  history_id?: number | null;
}
export interface XAIResult {
  requested_method?: string;
  method: string;
  xai_scope?: "patch" | "full" | string | null;
  width: number;
  height: number;
  overlay_png_base64: string;
  combined_png_base64: string;
  has_detections?: boolean;
  used_conf_threshold?: number;
  used_target_layers?: number[];
  fallback_reason?: string | null;
  fallback_details?: string | null;
}
export interface PreviewImageResponse {
  file_type: string;
  source_width: number;
  source_height: number;
  preview_width: number;
  preview_height: number;
  resolution_x: number;
  resolution_y: number;
  resolution_unit?: string | null;
  crs?: string | null;
  parcel_area_hectares?: number | null;
  location_center_lat?: number | null;
  location_center_lon?: number | null;
  acquisition_date?: string | null;
  preview_png_base64: string;
}
export interface JobAcceptedResponse { job_id: string; job_type: JobType; status: JobStatus; created_at: string; }
export interface JobStatusResponse<T = Record<string, unknown>> {
  job_id: string; job_type: JobType; status: JobStatus; progress: number;
  created_at: string; started_at?: string | null; ended_at?: string | null;
  error?: string | null; result?: T | null;
}
export function toDataUrl(base64Png: string): string { return `data:image/png;base64,${base64Png}`; }

export interface AnalysisHistoryItem {
  id: number;
  user_id: string | null;
  username: string | null;
  filename: string;
  original_filename?: string | null;
  executed_at: string;
  detection_count: number;
  all_detection_count: number;
  mean_confidence: number | null;
  estimated_missing: number;
  processing_time_s: number | null;
  display_confidence_threshold?: number | null;
  capture_confidence_threshold?: number | null;
  typical_vine_width?: number | null;
  slice_size?: number | null;
  overlap_ratio?: number | null;
  model_path?: string | null;
  source_width?: number | null;
  source_height?: number | null;
  file_type?: string | null;
  resolution_x?: number | null;
  resolution_y?: number | null;
  resolution_unit?: string | null;
  crs?: string | null;
  transform?: number[] | null;
  parcel_area_hectares?: number | null;
  location_center_lat?: number | null;
  location_center_lon?: number | null;
  acquisition_date?: string | null;
  has_source_artifact?: boolean;
  saved: boolean;
  source_file_size_bytes?: number | null;
}

export interface QuotaResponse {
  used_bytes: number;
  total_bytes: number;
}

export interface SaveParcelResponse {
  saved: boolean;
  used_bytes: number;
  total_bytes: number;
}

export interface AnalysisHistoryDetail extends AnalysisHistoryItem {
  preview_png_b64: string | null;
  result_json: string | null;
}
