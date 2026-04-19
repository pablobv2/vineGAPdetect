from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def init_db(db_url: str) -> tuple[Engine, sessionmaker[Session]]:
    """Create the engine, run CREATE TABLE IF NOT EXISTS for all models, and return
    the engine and a session factory. Call once at application startup."""
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    session_factory: sessionmaker[Session] = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    # Import models so their metadata is registered before create_all.
    import app.db.models  # noqa: F401
    Base.metadata.create_all(engine)
    _migrate_columns(engine)
    _backfill_history_metadata(engine)
    _backfill_saved_status(engine)
    _cleanup_legacy_png_payloads(engine)
    cleanup_old_unsaved(engine)
    return engine, session_factory


def _migrate_columns(engine: Engine) -> None:
    """Add columns that were introduced after the initial schema creation."""
    from sqlalchemy import text
    new_cols = [
        ("analysis_history", "result_json",                  "TEXT"),
        ("analysis_history", "original_filename",            "VARCHAR(255)"),
        ("analysis_history", "all_detection_count",          "INTEGER NOT NULL DEFAULT 0"),
        ("analysis_history", "capture_confidence_threshold", "FLOAT"),
        ("analysis_history", "display_confidence_threshold", "FLOAT"),
        ("analysis_history", "typical_vine_width",           "FLOAT"),
        ("analysis_history", "slice_size",                   "INTEGER"),
        ("analysis_history", "overlap_ratio",                "FLOAT"),
        ("analysis_history", "model_path",                   "VARCHAR(512)"),
        ("analysis_history", "source_width",                 "INTEGER"),
        ("analysis_history", "source_height",                "INTEGER"),
        ("analysis_history", "file_type",                    "VARCHAR(32)"),
        ("analysis_history", "resolution_x",                 "FLOAT"),
        ("analysis_history", "resolution_y",                 "FLOAT"),
        ("analysis_history", "resolution_unit",              "VARCHAR(32)"),
        ("analysis_history", "crs",                          "TEXT"),
        ("analysis_history", "transform_json",               "TEXT"),
        ("analysis_history", "parcel_area_hectares",         "FLOAT"),
        ("analysis_history", "location_center_lat",          "FLOAT"),
        ("analysis_history", "location_center_lon",          "FLOAT"),
        ("analysis_history", "acquisition_date",             "VARCHAR(64)"),
        ("analysis_history", "source_artifact_path",         "VARCHAR(1024)"),
        ("analysis_history", "source_file_size_bytes",        "INTEGER"),
        ("analysis_history", "source_sha256",                 "VARCHAR(64)"),
        ("analysis_history", "saved",                         "BOOLEAN NOT NULL DEFAULT 0"),
    ]
    with engine.connect() as conn:
        for table, col, col_type in new_cols:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass  # column already exists


def _backfill_history_metadata(engine: Engine) -> None:
    """Populate newly introduced history fields from legacy result_json snapshots."""
    from sqlalchemy import text

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, filename, result_json FROM analysis_history "
            "WHERE original_filename IS NULL "
            "OR all_detection_count = 0 "
            "OR source_width IS NULL"
        )).mappings().all()

        for row in rows:
            result: dict | None = None
            if row["result_json"]:
                try:
                    parsed = json.loads(row["result_json"])
                    result = parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    result = None

            image_meta = result.get("image_meta", {}) if result else {}
            parameters = result.get("parameters", {}) if result else {}
            detections = result.get("detections", []) if result else []
            summary_all = result.get("summary_all", {}) if result else {}
            all_detection_count = (
                summary_all.get("detections_count")
                if isinstance(summary_all, dict)
                else None
            )
            if all_detection_count is None and isinstance(detections, list):
                all_detection_count = len(detections)

            conn.execute(text(
                """
                UPDATE analysis_history
                SET
                    original_filename = COALESCE(original_filename, :original_filename),
                    all_detection_count = CASE
                        WHEN all_detection_count = 0 THEN :all_detection_count
                        ELSE all_detection_count
                    END,
                    capture_confidence_threshold = COALESCE(capture_confidence_threshold, :capture_confidence_threshold),
                    display_confidence_threshold = COALESCE(display_confidence_threshold, :display_confidence_threshold),
                    typical_vine_width = COALESCE(typical_vine_width, :typical_vine_width),
                    slice_size = COALESCE(slice_size, :slice_size),
                    overlap_ratio = COALESCE(overlap_ratio, :overlap_ratio),
                    model_path = COALESCE(model_path, :model_path),
                    source_width = COALESCE(source_width, :source_width),
                    source_height = COALESCE(source_height, :source_height),
                    file_type = COALESCE(file_type, :file_type),
                    resolution_x = COALESCE(resolution_x, :resolution_x),
                    resolution_y = COALESCE(resolution_y, :resolution_y),
                    resolution_unit = COALESCE(resolution_unit, :resolution_unit),
                    crs = COALESCE(crs, :crs),
                    transform_json = COALESCE(transform_json, :transform_json),
                    parcel_area_hectares = COALESCE(parcel_area_hectares, :parcel_area_hectares),
                    location_center_lat = COALESCE(location_center_lat, :location_center_lat),
                    location_center_lon = COALESCE(location_center_lon, :location_center_lon),
                    acquisition_date = COALESCE(acquisition_date, :acquisition_date)
                WHERE id = :id
                """
            ), {
                "id": row["id"],
                "original_filename": row["filename"],
                "all_detection_count": int(all_detection_count or 0),
                "capture_confidence_threshold": parameters.get("capture_confidence_threshold"),
                "display_confidence_threshold": parameters.get("display_confidence_threshold"),
                "typical_vine_width": parameters.get("typical_vine_width"),
                "slice_size": parameters.get("slice_size"),
                "overlap_ratio": parameters.get("overlap_ratio"),
                "model_path": parameters.get("model_path"),
                "source_width": image_meta.get("width"),
                "source_height": image_meta.get("height"),
                "file_type": image_meta.get("file_type"),
                "resolution_x": image_meta.get("resolution_x"),
                "resolution_y": image_meta.get("resolution_y"),
                "resolution_unit": image_meta.get("resolution_unit"),
                "crs": image_meta.get("crs"),
                "transform_json": json.dumps(image_meta.get("transform")) if image_meta.get("transform") else None,
                "parcel_area_hectares": image_meta.get("parcel_area_hectares"),
                "location_center_lat": image_meta.get("location_center_lat"),
                "location_center_lon": image_meta.get("location_center_lon"),
                "acquisition_date": image_meta.get("acquisition_date"),
            })


def _backfill_saved_status(engine: Engine) -> None:
    """Mark pre-quota records (those with no file-size tracked) as saved=True.
    They were auto-saved before the explicit-save feature was introduced."""
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE analysis_history SET saved=1 "
            "WHERE saved=0 AND source_file_size_bytes IS NULL "
            "AND source_artifact_path IS NOT NULL"
        ))


def _cleanup_legacy_png_payloads(engine: Engine) -> None:
    """Drop legacy base64 image payloads from the DB.

    Current saved parcels keep the source artifact and regenerate previews/XAI from it.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        for col in ("preview_png_b64", "xai_png_b64"):
            try:
                conn.execute(text(f"UPDATE analysis_history SET {col}=NULL WHERE {col} IS NOT NULL"))
            except Exception:
                pass


def cleanup_old_unsaved(engine: Engine) -> None:
    """Delete unsaved (draft) analysis records older than 2 hours and their artifacts."""
    from sqlalchemy import text
    from app.core.config import settings

    cutoff = datetime.utcnow() - timedelta(hours=2)
    with engine.begin() as conn:
        artifact_rows = conn.execute(text(
            "SELECT source_artifact_path FROM analysis_history "
            "WHERE saved=0 AND executed_at < :cutoff AND source_artifact_path IS NOT NULL"
        ), {"cutoff": cutoff}).mappings().all()
        conn.execute(text(
            "DELETE FROM analysis_history WHERE saved=0 AND executed_at < :cutoff"
        ), {"cutoff": cutoff})

    for row in artifact_rows:
        artifact_path = Path(row["source_artifact_path"])
        if not artifact_path.is_absolute():
            artifact_path = (settings.repo_root / artifact_path).resolve()
        if artifact_path.exists():
            try:
                artifact_path.unlink()
            except OSError:
                pass
