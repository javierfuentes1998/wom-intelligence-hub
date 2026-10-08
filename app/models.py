from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Location(Base):
    __tablename__ = "dim_location"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    address: Mapped[str | None] = mapped_column(String(180))
    city: Mapped[str | None] = mapped_column(String(80))
    source_system: Mapped[str] = mapped_column(String(30), default="DEMO")
    external_id: Mapped[str | None] = mapped_column(String(100))
    rooms: Mapped[list["Room"]] = relationship(back_populates="location")

class Room(Base):
    __tablename__ = "dim_room"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("dim_location.id"))
    name: Mapped[str] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    experience_type: Mapped[str | None] = mapped_column(String(60))
    source_system: Mapped[str] = mapped_column(String(30), default="DEMO")
    external_id: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[Location] = relationship(back_populates="rooms")
    __table_args__ = (UniqueConstraint("location_id", "name"),)

class GameMaster(Base):
    __tablename__ = "dim_game_master"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_name: Mapped[str] = mapped_column(String(80), default="GM DEMO")
    external_id: Mapped[str | None] = mapped_column(String(100))
    home_location_id: Mapped[str | None] = mapped_column(ForeignKey("dim_location.id"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    source_system: Mapped[str] = mapped_column(String(30), default="DEMO")

class ExpenseCategory(Base):
    __tablename__ = "dim_expense_category"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)

class Session(Base):
    __tablename__ = "fact_session"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("dim_room.id"))
    game_master_id: Mapped[str | None] = mapped_column(ForeignKey("dim_game_master.id"))
    second_game_master_id: Mapped[str | None] = mapped_column(ForeignKey("dim_game_master.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20))
    customers: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0)
    external_id: Mapped[str | None] = mapped_column(String(100), index=True)
    source_system: Mapped[str] = mapped_column(String(40), default="DEMO")
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    price_per_person: Mapped[float | None] = mapped_column(Float)
    deposit: Mapped[float] = mapped_column(Float, default=0)
    pending_amount: Mapped[float] = mapped_column(Float, default=0)
    discount: Mapped[float] = mapped_column(Float, default=0)
    coupon: Mapped[str | None] = mapped_column(String(80))
    refund: Mapped[float] = mapped_column(Float, default=0)
    payment_method: Mapped[str | None] = mapped_column(String(30))
    requires_double_gm: Mapped[bool] = mapped_column(Boolean, default=False)
    double_gm_source: Mapped[str | None] = mapped_column(String(20))

class Expense(Base):
    __tablename__ = "fact_expense"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    concept: Mapped[str] = mapped_column(String(160))
    category_id: Mapped[int] = mapped_column(ForeignKey("dim_expense_category.id"))
    amount: Mapped[float] = mapped_column(Float)
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("dim_location.id"))
    room_id: Mapped[str | None] = mapped_column(ForeignKey("dim_room.id"))
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    periodicity: Mapped[str | None] = mapped_column(String(30))
    recurrence_key: Mapped[str | None] = mapped_column(String(100), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    voided: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Review(Base):
    __tablename__ = "fact_review"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    review_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(40))
    location_id: Mapped[str | None] = mapped_column(ForeignKey("dim_location.id"))
    room_id: Mapped[str | None] = mapped_column(ForeignKey("dim_room.id"))
    rating: Mapped[float | None] = mapped_column(Float)
    original_text: Mapped[str] = mapped_column(Text)
    processed_text: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[str] = mapped_column(String(20))
    sentiment_score: Mapped[float] = mapped_column(Float)
    topics: Mapped[str] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(String(30), default="DEMO")
    external_id: Mapped[str | None] = mapped_column(String(100), index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ReviewSourceConfig(Base):
    __tablename__ = "review_source_config"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    provider: Mapped[str] = mapped_column(String(60), default="google_business_profile")
    status: Mapped[str] = mapped_column(String(40), default="PENDING_AUTHORIZATION")
    account_id: Mapped[str | None] = mapped_column(String(160))
    oauth_scope: Mapped[str] = mapped_column(String(180), default="https://www.googleapis.com/auth/business.manage")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    received_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    modified_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    expected_refresh_minutes: Mapped[int] = mapped_column(Integer, default=360)

class ReviewLocationMap(Base):
    __tablename__ = "review_location_map"
    google_location_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    wom_location_id: Mapped[str | None] = mapped_column(ForeignKey("dim_location.id"))
    google_name: Mapped[str | None] = mapped_column(String(180))
    google_address: Mapped[str | None] = mapped_column(String(300))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class RawReview(Base):
    __tablename__ = "raw_review"
    id: Mapped[str] = mapped_column(String(260), primary_key=True)
    source: Mapped[str] = mapped_column(String(60), default="google_business_profile")
    external_review_id: Mapped[str] = mapped_column(String(180), index=True)
    google_location_id: Mapped[str] = mapped_column(String(180), index=True)
    wom_location_id: Mapped[str | None] = mapped_column(ForeignKey("dim_location.id"), index=True)
    reviewer_display_name: Mapped[str | None] = mapped_column(String(160))
    star_rating: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    create_time: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    update_time: Mapped[datetime | None] = mapped_column(DateTime)
    reply: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_payload: Mapped[str] = mapped_column(Text)
    ingestion_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class ProcessedReview(Base):
    __tablename__ = "processed_review"
    raw_review_id: Mapped[str] = mapped_column(ForeignKey("raw_review.id"), primary_key=True)
    language: Mapped[str | None] = mapped_column(String(12))
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    sentiment_label: Mapped[str | None] = mapped_column(String(30))
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    aspects: Mapped[str] = mapped_column(Text, default="[]")
    entities: Mapped[str] = mapped_column(Text, default="[]")
    room_id: Mapped[str | None] = mapped_column(ForeignKey("dim_room.id"))
    room_method: Mapped[str | None] = mapped_column(String(40))
    room_confidence: Mapped[float | None] = mapped_column(Float)
    star_text_discrepancy: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_status: Mapped[str] = mapped_column(String(30), default="analysis_pending", index=True)
    analyzer_method: Mapped[str] = mapped_column(String(60), default="hybrid_rules")
    analyzer_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)
    analysis_error: Mapped[str | None] = mapped_column(Text)

class ReviewSyncRun(Base):
    __tablename__ = "review_sync_run"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source: Mapped[str] = mapped_column(String(60))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), default="RUNNING")
    received: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    modified: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

class ReviewGoldSnapshot(Base):
    __tablename__ = "review_gold_snapshot"
    scope_key: Mapped[str] = mapped_column(String(180), primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    analyzer_version: Mapped[str] = mapped_column(String(20))
    payload: Mapped[str] = mapped_column(Text)

class GameMasterRate(Base):
    __tablename__ = "dim_game_master_rate"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("dim_location.id"))
    room_id: Mapped[str | None] = mapped_column(ForeignKey("dim_room.id"))
    amount: Mapped[float] = mapped_column(Float)
    rate_type: Mapped[str] = mapped_column(String(20), default="normal")
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Season(Base):
    __tablename__ = "dim_season"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class RoomSchedule(Base):
    __tablename__ = "room_schedule"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("dim_room.id"))
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[str] = mapped_column(String(5))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    season_id: Mapped[int | None] = mapped_column(ForeignKey("dim_season.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class RecurringExpensePlan(Base):
    __tablename__ = "recurring_expense_plan"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    concept: Mapped[str] = mapped_column(String(160))
    category_id: Mapped[int] = mapped_column(ForeignKey("dim_expense_category.id"))
    amount: Mapped[float] = mapped_column(Float)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("dim_location.id"))
    room_id: Mapped[str | None] = mapped_column(ForeignKey("dim_room.id"))
    periodicity: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Alert(Base):
    __tablename__ = "insight_alert"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    category: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    explanation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    seen: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    alert_key: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    current_value: Mapped[float | None] = mapped_column(Float)
    baseline_value: Mapped[float | None] = mapped_column(Float)
    deviation: Mapped[float | None] = mapped_column(Float)
    evidence_strength: Mapped[float] = mapped_column(Float, default=0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0)

class DataSource(Base):
    __tablename__ = "data_source"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(40))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    expected_refresh_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    last_error: Mapped[str | None] = mapped_column(Text)
    strategy: Mapped[str] = mapped_column(String(30), default="manual")

class DataImportRun(Base):
    __tablename__ = "data_import_run"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(40), index=True)
    datasets: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

class User(Base):
    __tablename__ = "app_user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
