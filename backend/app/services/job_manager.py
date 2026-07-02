from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from queue import Empty, Queue
from threading import Event, Lock, Thread
from uuid import uuid4

from app.schemas.api import JobStatus, JobType


ProgressCallback = Callable[[int], None]
JobHandler = Callable[[dict, ProgressCallback], dict]


@dataclass
class JobRecord:
    """Estado serializable de un trabajo asincrono ejecutado por la API."""
    job_id: str
    job_type: JobType
    status: JobStatus = JobStatus.queued
    progress: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None
    result: dict | None = None


@dataclass
class _JobRequest:
    job_id: str
    handler: JobHandler
    payload: dict


class JobManager:
    """Ejecuta trabajos en segundo plano y conserva progreso, errores y resultados temporales.

    Desacopla las operaciones lentas de la peticion HTTP: las rutas crean un
    job, el worker procesa inferencia o XAI, y el frontend consulta el estado
    mediante polling. Incluye limpieza periodica para no mantener resultados
    temporales indefinidamente en memoria.
    """
    def __init__(self, cleanup_seconds: int, cleanup_interval_seconds: int = 60) -> None:
        self.cleanup_seconds = cleanup_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._jobs: dict[str, JobRecord] = {}
        self._queue: Queue[_JobRequest] = Queue()
        self._lock = Lock()
        self._stop_event = Event()
        self._worker_thread: Thread | None = None
        self._cleanup_thread: Thread | None = None

    def start(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = Thread(target=self._worker_loop, name="job-worker", daemon=True)
        self._cleanup_thread = Thread(target=self._cleanup_loop, name="job-cleanup", daemon=True)
        self._worker_thread.start()
        self._cleanup_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2)
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=2)

    def submit(self, job_type: JobType, handler: JobHandler, payload: dict) -> JobRecord:
        job_id = str(uuid4())
        record = JobRecord(job_id=job_id, job_type=job_type)
        with self._lock:
            self._jobs[job_id] = record
        self._queue.put(_JobRequest(job_id=job_id, handler=handler, payload=payload))
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return False
            if record.status not in {JobStatus.completed, JobStatus.failed}:
                return False
            self._jobs.pop(job_id, None)
            return True

    def _set_progress(self, job_id: str, value: int) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return
            record.progress = min(max(int(value), 0), 100)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                request = self._queue.get(timeout=0.5)
            except Empty:
                continue

            with self._lock:
                record = self._jobs.get(request.job_id)
                if record is None:
                    continue
                record.status = JobStatus.running
                record.started_at = datetime.utcnow()

            def progress_cb(value: int) -> None:
                self._set_progress(request.job_id, value)

            try:
                result = request.handler(request.payload, progress_cb)
                with self._lock:
                    record = self._jobs.get(request.job_id)
                    if record is None:
                        continue
                    record.status = JobStatus.completed
                    record.progress = 100
                    record.result = result
                    record.ended_at = datetime.utcnow()
            except Exception as exc:
                with self._lock:
                    record = self._jobs.get(request.job_id)
                    if record is None:
                        continue
                    record.status = JobStatus.failed
                    record.error = str(exc)
                    record.ended_at = datetime.utcnow()
            finally:
                self._queue.task_done()

    def _cleanup_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(self.cleanup_interval_seconds)
            if self._stop_event.is_set():
                return
            threshold = datetime.utcnow() - timedelta(seconds=self.cleanup_seconds)
            with self._lock:
                to_delete = [
                    job_id
                    for job_id, record in self._jobs.items()
                    if record.status in {JobStatus.completed, JobStatus.failed}
                    and record.ended_at is not None
                    and record.ended_at < threshold
                ]
                for job_id in to_delete:
                    self._jobs.pop(job_id, None)

