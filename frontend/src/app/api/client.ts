import type {
  AnalysisHistoryDetail,
  AnalysisHistoryItem,
  AuthSession,
  CreateUserPayload,
  JobAcceptedResponse,
  JobStatusResponse,
  LoginPayload,
  PreviewImageResponse,
  QuotaResponse,
  SaveParcelResponse,
  UpdateUserPayload,
  UserPublic,
} from "./types";

const DEFAULT_API_BASE_URL =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
const API_PREFIX = "/api/v1";
let authToken: string | null = null;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

export function setAuthToken(token: string | null): void { authToken = token; }
export function clearAuthToken(): void { authToken = null; }

function assertJobAccepted(payload: unknown): JobAcceptedResponse {
  if (!payload || typeof payload !== "object") throw new Error("Respuesta inválida del backend al crear el job.");
  const data = payload as Partial<JobAcceptedResponse>;
  if (!data.job_id || !isUuid(String(data.job_id))) throw new Error("El backend no devolvió un job_id válido.");
  if (!data.job_type || !data.status || !data.created_at) throw new Error("Respuesta incompleta al crear el job.");
  return data as JobAcceptedResponse;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { const data = await response.json(); if (data?.detail) detail = String(data.detail); } catch {}
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return null as T;
  }
  return response.json() as Promise<T>;
}

export async function loginUser(payload: LoginPayload): Promise<AuthSession> {
  return request<AuthSession>("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
}
export async function getCurrentUser(): Promise<UserPublic> {
  return request<UserPublic>("/auth/me", { method: "GET" });
}
export async function logoutUser(): Promise<void> {
  await request<{ detail: string }>("/auth/logout", { method: "POST" });
}
export async function listUsers(): Promise<UserPublic[]> {
  return request<UserPublic[]>("/users", { method: "GET" });
}
export async function getManagedUser(userId: string): Promise<UserPublic> {
  return request<UserPublic>(`/users/${userId}`, { method: "GET" });
}
export async function createManagedUser(payload: CreateUserPayload): Promise<UserPublic> {
  return request<UserPublic>("/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
}
export async function updateManagedUser(userId: string, payload: UpdateUserPayload): Promise<UserPublic> {
  return request<UserPublic>(`/users/${userId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
}
export async function resetManagedUserPassword(userId: string, newPassword: string): Promise<void> {
  await request<{ detail: string }>(`/users/${userId}/reset-password`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ new_password: newPassword }) });
}
export async function deleteManagedUser(userId: string): Promise<void> {
  await request<{ detail: string }>(`/users/${userId}`, { method: "DELETE" });
}
export async function createInferenceJob(file: File, options?: { confidenceThreshold?: number; displayConfidenceThreshold?: number; overlapRatio?: number; vineWidth?: number; sliceSize?: number }): Promise<JobAcceptedResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("confidence_threshold", String(options?.confidenceThreshold ?? 0.35));
  form.append("display_confidence_threshold", String(options?.displayConfidenceThreshold ?? options?.confidenceThreshold ?? 0.55));
  form.append("overlap_ratio", String(options?.overlapRatio ?? 0.2));
  form.append("typical_vine_width", String(options?.vineWidth ?? 1.5));
  form.append("slice_size", String(options?.sliceSize ?? 640));
  return assertJobAccepted(await request<unknown>("/jobs/inference", { method: "POST", body: form }));
}
export async function generatePreview(file: File): Promise<PreviewImageResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<PreviewImageResponse>("/preview", { method: "POST", body: form });
}
export async function createXaiJob(file: File, options: {
  method: "eigencam";
  scope?: "patch" | "full";
  targetLayers?: number[];
  confThreshold?: number;
  imgsz?: number;
  cx?: number;
  cy?: number;
  focusBbox?: [number, number, number, number];
  focusConfidence?: number;
}): Promise<JobAcceptedResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("method", options.method);
  form.append("xai_scope", options.scope ?? "patch");
  form.append("target_layers", (options.targetLayers ?? [18]).join(","));
  form.append("conf_threshold", String(options.confThreshold ?? 0.55));
  form.append("imgsz", String(options.imgsz ?? 640));
  if (options.cx !== undefined) form.append("cx", String(Math.round(options.cx)));
  if (options.cy !== undefined) form.append("cy", String(Math.round(options.cy)));
  if (options.focusBbox) form.append("focus_bbox", JSON.stringify(options.focusBbox.map(value => Math.round(value))));
  if (options.focusConfidence !== undefined) form.append("focus_confidence", String(options.focusConfidence));
  return assertJobAccepted(await request<unknown>("/jobs/xai", { method: "POST", body: form }));
}

export async function createHistoryXaiJob(historyId: number, options: {
  method: "eigencam";
  scope?: "patch" | "full";
  detectionId?: number | null;
  targetLayers?: number[];
  confThreshold?: number;
  imgsz?: number;
}): Promise<JobAcceptedResponse> {
  const form = new FormData();
  form.append("method", options.method);
  form.append("xai_scope", options.scope ?? "patch");
  form.append("target_layers", (options.targetLayers ?? [18]).join(","));
  form.append("conf_threshold", String(options.confThreshold ?? 0.55));
  form.append("imgsz", String(options.imgsz ?? 640));
  if (options.detectionId !== undefined && options.detectionId !== null) {
    form.append("detection_id", String(options.detectionId));
  }
  return assertJobAccepted(await request<unknown>(`/history/${historyId}/xai`, { method: "POST", body: form }));
}
export async function getJob<T = Record<string, unknown>>(jobId: string): Promise<JobStatusResponse<T>> {
  if (!isUuid(jobId)) throw new Error(`job_id inválido: ${jobId}`);
  return request<JobStatusResponse<T>>(`/jobs/${jobId}`, { method: "GET" });
}

export async function getHistory(limit = 200): Promise<AnalysisHistoryItem[]> {
  return request<AnalysisHistoryItem[]>(`/history?limit=${limit}`, { method: "GET" });
}

export async function getHistoryItem(id: number): Promise<AnalysisHistoryDetail> {
  return request<AnalysisHistoryDetail>(`/history/${id}`, { method: "GET" });
}

export async function deleteHistoryItem(id: number): Promise<void> {
  await request<void>(`/history/${id}`, { method: "DELETE" });
}

export async function saveParcel(historyId: number): Promise<SaveParcelResponse> {
  return request<SaveParcelResponse>(`/history/${historyId}/save`, { method: "POST" });
}

export async function getQuota(): Promise<QuotaResponse> {
  return request<QuotaResponse>("/history/quota", { method: "GET" });
}

export interface ExportDetectionPayload {
  id: number;
  class_name: string;
  confidence: number;
  obb_polygon: number[][];
  estimated_missing_vines: number;
}

export async function exportDetectionsGpkg(payload: {
  detections: ExportDetectionPayload[];
  transform: number[];
  crs: string;
  parcelName?: string | null;
  confThreshold?: number;
}): Promise<Blob> {
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);

  const body = JSON.stringify({
    detections: payload.detections,
    transform: payload.transform,
    crs: payload.crs,
    parcel_name: payload.parcelName ?? null,
    conf_threshold: payload.confThreshold ?? 0,
  });

  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/export/detections-gpkg`, {
    method: "POST",
    headers,
    body,
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { const data = await response.json(); if (data?.detail) detail = String(data.detail); } catch {}
    throw new ApiError(response.status, detail);
  }
  return response.blob();
}
