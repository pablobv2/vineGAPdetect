from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.db.database import Base


class UserModel(Base):
    __tablename__ = "users"

    id            = Column(String(36),  primary_key=True)
    username      = Column(String(50),  unique=True, nullable=False, index=True)
    full_name     = Column(String(120), nullable=False)
    role          = Column(String(20),  nullable=False)          # "admin" | "operator"
    is_active     = Column(Boolean,     nullable=False, default=True)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime,    nullable=False)
    updated_at    = Column(DateTime,    nullable=False)
    last_login_at = Column(DateTime,    nullable=True)


class SessionModel(Base):
    __tablename__ = "sessions"

    token      = Column(String(64), primary_key=True)
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime,   nullable=False, index=True)


class AnalysisHistory(Base):
    """One row per completed inference job."""
    __tablename__ = "analysis_history"

    id                           = Column(Integer,     primary_key=True, autoincrement=True)
    user_id                      = Column(String(36),  ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    filename                     = Column(String(255), nullable=False)  # legacy alias for original_filename
    original_filename            = Column(String(255), nullable=True)
    executed_at                  = Column(DateTime,    nullable=False, index=True)
    detection_count              = Column(Integer,     nullable=False, default=0)
    all_detection_count          = Column(Integer,     nullable=False, default=0)
    mean_confidence              = Column(Float,       nullable=True)
    estimated_missing            = Column(Integer,     nullable=False, default=0)
    processing_time_s            = Column(Float,       nullable=True)
    capture_confidence_threshold = Column(Float,       nullable=True)
    display_confidence_threshold = Column(Float,       nullable=True)
    typical_vine_width           = Column(Float,       nullable=True)
    slice_size                   = Column(Integer,     nullable=True)
    overlap_ratio                = Column(Float,       nullable=True)
    model_path                   = Column(String(512), nullable=True)
    source_width                 = Column(Integer,     nullable=True)
    source_height                = Column(Integer,     nullable=True)
    file_type                    = Column(String(32),  nullable=True)
    resolution_x                 = Column(Float,       nullable=True)
    resolution_y                 = Column(Float,       nullable=True)
    resolution_unit              = Column(String(32),  nullable=True)
    crs                          = Column(Text,        nullable=True)
    transform_json               = Column(Text,        nullable=True)
    parcel_area_hectares         = Column(Float,       nullable=True)
    location_center_lat          = Column(Float,       nullable=True)
    location_center_lon          = Column(Float,       nullable=True)
    acquisition_date             = Column(String(64),  nullable=True)
    source_artifact_path         = Column(String(1024), nullable=True)  # local original upload used for history XAI
    source_file_size_bytes       = Column(BigInteger,  nullable=True)  # size of the original uploaded file
    source_sha256                = Column(String(64),  nullable=True, index=True)  # hash of original uploaded file
    result_json                  = Column(Text,        nullable=True)  # full InferenceResult as JSON
    saved                        = Column(Boolean,     nullable=False, default=False)  # user explicitly saved this parcel
