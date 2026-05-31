import { useEffect, useRef, useState } from "react";
import { ApiError, getJob } from "../api/client";
import type { JobStatusResponse } from "../api/types";

export function useJobPolling<T>(jobId: string | null, enabled = true, intervalMs = 800) {
  const [job, setJob] = useState<JobStatusResponse<T> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!jobId || !enabled) { setIsPolling(false); return; }
    let cancelled = false;
    const stop = () => {
      if (intervalRef.current !== null) { window.clearInterval(intervalRef.current); intervalRef.current = null; }
      setIsPolling(false);
    };
    const tick = async () => {
      try {
        const data = await getJob<T>(jobId);
        if (cancelled) return;
        setJob(data);
        if (data.status === "completed" || data.status === "failed") stop();
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setError("Job no encontrado. Es posible que el backend se haya reiniciado.");
        } else {
          setError(err instanceof Error ? err.message : "Error consultando estado del job");
        }
        stop();
      }
    };
    setError(null);
    setJob(null);
    setIsPolling(true);
    tick();
    intervalRef.current = window.setInterval(tick, intervalMs);
    return () => { cancelled = true; stop(); };
  }, [jobId, enabled, intervalMs]);

  return { job, error, isPolling };
}
