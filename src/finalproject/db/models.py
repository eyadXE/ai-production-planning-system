"""SQLAlchemy models — mirrors OUSUS/data_schema.md.

Conventions:
- money is stored in EGP (canonical); fx_rates converts for display only
- statuses are plain strings (validated at service layer, not DB level)
- every estimate figure carries a handbook-clause citation
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finalproject.db.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)  # AC-01
    name: Mapped[str] = mapped_column(String(120))
    tier: Mapped[str] = mapped_column(String(16))  # key | standard | retail
    margin_floor: Mapped[float] = mapped_column(Float)

    users: Mapped[list["User"]] = relationship(back_populates="account")
    projects: Mapped[list["Project"]] = relationship(back_populates="account")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16))  # client | engineer | manager | viewer
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)

    account: Mapped["Account | None"] = relationship(back_populates="users")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)  # SHS-50
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(32), default="steel")
    unit: Mapped[str] = mapped_column(String(16))  # bar | sheet | kg ...
    price_egp: Mapped[float] = mapped_column(Float)
    stock_qty: Mapped[float] = mapped_column(Float)
    lead_time_weeks: Mapped[int] = mapped_column(Integer)
    substitution_allowed: Mapped[bool] = mapped_column(default=False)


class CapacityWeek(Base):
    __tablename__ = "capacity_weeks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_label: Mapped[str] = mapped_column(String(12), unique=True)  # 2026-W35
    start_date: Mapped[date] = mapped_column(Date)
    total_hours: Mapped[float] = mapped_column(Float)
    booked_hours: Mapped[float] = mapped_column(Float)

    bookings: Mapped[list["ScheduleBooking"]] = relationship(back_populates="week")


class Spec(Base):
    __tablename__ = "specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)  # J-001
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    title: Mapped[str] = mapped_column(String(200), default="")
    raw_text: Mapped[str] = mapped_column(Text)
    structured_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="file")  # file | chat_intake
    status: Mapped[str] = mapped_column(
        String(24), default="approved"
    )  # draft | pending_review | info_requested | approved | rejected
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    account: Mapped["Account"] = relationship()
    reviewer: Mapped["User | None"] = relationship()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)  # P-101 / J-014
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    spec_id: Mapped[int | None] = mapped_column(ForeignKey("specs.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    stage: Mapped[str] = mapped_column(String(32))  # enquiry .. closed
    status: Mapped[str] = mapped_column(String(24))  # on_track | overdue | blocked_material
    required_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_finish: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_engineer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True)
    release_status: Mapped[str] = mapped_column(
        String(16), default="na"
    )  # na | queued | released | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    account: Mapped["Account"] = relationship(back_populates="projects")
    spec: Mapped["Spec | None"] = relationship()
    assigned_engineer: Mapped["User | None"] = relationship()
    stage_events: Mapped[list["StageEvent"]] = relationship(back_populates="project")
    estimates: Mapped[list["Estimate"]] = relationship(back_populates="project")
    bookings: Mapped[list["ScheduleBooking"]] = relationship(back_populates="project")


class StageEvent(Base):
    __tablename__ = "stage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    stage: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[date] = mapped_column(Date)
    planned_finish_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    finished_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="stage_events")


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    decision: Mapped[str] = mapped_column(String(24))
    material_cost_egp: Mapped[float] = mapped_column(Float, default=0.0)
    consumables_egp: Mapped[float] = mapped_column(Float, default=0.0)
    fab_hours: Mapped[float] = mapped_column(Float, default=0.0)
    install_hours: Mapped[float] = mapped_column(Float, default=0.0)
    labour_cost_egp: Mapped[float] = mapped_column(Float, default=0.0)
    margin_applied: Mapped[float] = mapped_column(Float, default=0.0)
    final_price_egp: Mapped[float] = mapped_column(Float, default=0.0)
    citations_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="estimates")
    bom_lines: Mapped[list["BomLine"]] = relationship(back_populates="estimate")
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_estimate_version"),)


class BomLine(Base):
    __tablename__ = "bom_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    qty: Mapped[float] = mapped_column(Float)
    waste_pct: Mapped[float] = mapped_column(Float, default=0.0)
    line_cost_egp: Mapped[float] = mapped_column(Float)
    clause_citation: Mapped[str] = mapped_column(String(32), default="")

    estimate: Mapped["Estimate"] = relationship(back_populates="bom_lines")
    material: Mapped["Material"] = relationship()


class ScheduleBooking(Base):
    __tablename__ = "schedule_bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    capacity_week_id: Mapped[int] = mapped_column(ForeignKey("capacity_weeks.id"))
    hours: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(16))  # fab | install | galvanising

    project: Mapped["Project"] = relationship(back_populates="bookings")
    week: Mapped["CapacityWeek"] = relationship(back_populates="bookings")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_type: Mapped[str] = mapped_column(String(32))  # plan_release | material_order | margin_override
    entity_id: Mapped[int] = mapped_column(Integer)  # polymorphic target id
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(16))  # approved | rejected
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    approver: Mapped["User"] = relationship()


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    purpose: Mapped[str] = mapped_column(String(24))  # spec_intake | plan_qa
    collected_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | submitted
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(16))  # client | assistant | engineer
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    to_email: Mapped[str] = mapped_column(String(160), default="")
    template: Mapped[str] = mapped_column(String(48))  # plan_accepted | ...
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued | sent | failed
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class HandbookClause(Base):
    __tablename__ = "handbook_clauses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clause_no: Mapped[str] = mapped_column(String(8), unique=True)  # 2.2
    title: Mapped[str] = mapped_column(String(200))
    body_text: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(String(48), default="")


class FxRate(Base):
    __tablename__ = "fx_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    currency: Mapped[str] = mapped_column(String(8), unique=True)  # SAR | USD
    egp_per_unit: Mapped[float] = mapped_column(Float)  # 1 unit of currency = X EGP
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Product(Base):
    """Catalog product — mirrors the Ousus product lines from ousus.com."""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(48))       # Carbon Steel, ...
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    image: Mapped[str] = mapped_column(String(200), default="")
    catalogue_url: Mapped[str] = mapped_column(String(300), default="")
    # estimation mapping; null => custom engineering required (manual quote)
    est_kind: Mapped[str | None] = mapped_column(String(24), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="count")
