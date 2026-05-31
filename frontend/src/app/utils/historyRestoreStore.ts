import type { HistoryRestoreData } from "../hooks/useDashboardState";

let _pending: HistoryRestoreData | null = null;
const STORAGE_KEY = "vinegapdetect.pendingHistoryRestore";

export function setPendingHistoryRestore(data: HistoryRestoreData): void {
  _pending = data;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // Large XAI previews can exceed browser quota; the in-memory handoff still works.
  }
}

/** Returns the pending restore and clears it (single-use). */
export function consumePendingHistoryRestore(): HistoryRestoreData | null {
  let data = _pending;
  _pending = null;
  if (!data) {
    try {
      const raw = window.sessionStorage.getItem(STORAGE_KEY);
      data = raw ? JSON.parse(raw) as HistoryRestoreData : null;
    } catch {
      data = null;
    }
  }
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {}
  return data;
}

export function clearPendingHistoryRestore(): void {
  _pending = null;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {}
}
