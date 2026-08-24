"""Tracking: stages, overdue detection, daily summary (handbook Section 4)."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalproject.db.models import (
    Approval,
    CapacityWeek,
    Estimate,
    Project,
    StageEvent,
)

# Clause 4.1 — the stages, in order
STAGES = (
    "Award",
    "Engineering",
    "Procurement",
    "Production Planning",
    "Fabrication",
    "Quality Inspection",
    "Finishing",
    "Delivery",
    "Installation",
    "Closed",
)


class TrackingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def current_event(session: Session, project: Project) -> StageEvent | None:
    return session.scalar(
        select(StageEvent)
        .where(StageEvent.project_id == project.id,
               StageEvent.finished_at.is_(None))
        .order_by(StageEvent.id.desc())
    )


def is_overdue(project: Project, event: StageEvent | None) -> bool:
    """Clause 4.2 — overdue when today is past the current stage's plan."""
    if project.status == "overdue":
        return True
    return bool(
        event and event.planned_finish_at and date.today() > event.planned_finish_at
    )


def advance_stage(session: Session, project: Project,
                  next_stage: str | None = None) -> Project:
    """Move to the next (or explicit) stage; records dates per clause 4.2."""
    event = current_event(session, project)
    idx = STAGES.index(project.stage) if project.stage in STAGES else 0

    target = next_stage or (STAGES[idx + 1] if idx + 1 < len(STAGES) else None)
    if target is None:
        raise TrackingError("project already at final stage")
    if target not in STAGES:
        raise TrackingError(f"unknown stage '{target}'", 404)
    if target != "Closed" and STAGES.index(target) != idx + 1:
        raise TrackingError(
            f"cannot jump from '{project.stage}' to '{target}' — stages are "
            "sequential and inspection cannot be bypassed (4.3)")

    today = date.today()
    if event:
        event.finished_at = today
    project.stage = target
    if target != "Closed":
        session.add(
            StageEvent(project_id=project.id, stage=target, started_at=today)
        )
    session.commit()
    session.refresh(project)
    return project


def overdue_projects(session: Session) -> list[dict]:
    out = []
    for p in session.scalars(select(Project)).all():
        ev = current_event(session, p)
        if is_overdue(p, ev):
            out.append({
                "code": p.code,
                "title": p.title,
                "stage": p.stage,
                "planned_finish": (ev.planned_finish_at.isoformat()
                                   if ev and ev.planned_finish_at else None),
            })
    return out


def blocked_projects(session: Session) -> list[dict]:
    return [
        {"code": p.code, "title": p.title, "stage": p.stage}
        for p in session.scalars(
            select(Project).where(Project.status == "blocked_material")
        ).all()
    ]


def capacity_ahead(session: Session, horizon_weeks: int = 6) -> dict:
    rows = session.scalars(
        select(CapacityWeek).order_by(CapacityWeek.start_date)
    ).all()
    today = date.today()
    upcoming = [w for w in rows if w.start_date + timedelta(days=6) >= today]
    free = lambda w: w.total_hours - w.booked_hours  # noqa: E731
    fully_booked = [w.week_label for w in upcoming if free(w) <= 0]
    # "first meaningful free capacity" = when the backlog clears:
    # the first week with room after the last fully-booked week.
    first_free = None
    if fully_booked:
        last_blocked_idx = max(
            i for i, w in enumerate(upcoming) if w.week_label in fully_booked
        )
        for w in upcoming[last_blocked_idx + 1:]:
            if free(w) > 0:
                first_free = w.week_label
                break
    else:
        for w in upcoming:
            if free(w) >= w.total_hours * 0.5:
                first_free = w.week_label
                break
    return {
        "weeks": [
            {"week": w.week_label, "free_hours": free(w),
             "total_hours": w.total_hours}
            for w in upcoming[:horizon_weeks]
        ],
        "fully_booked_weeks": fully_booked,
        "first_meaningful_free_week": first_free,
    }


def daily_summary(session: Session) -> dict:
    """Clause 4.4 draft — every figure from tracking data; queued, never sent."""
    projects = session.scalars(select(Project)).all()
    by_stage: dict[str, int] = {s: 0 for s in STAGES}
    for p in projects:
        by_stage[p.stage] = by_stage.get(p.stage, 0) + 1

    queued = session.scalars(
        select(Approval).where(Approval.decision == "pending")
    ).all()

    return {
        "type": "DRAFT_SUMMARY",
        "projects_by_stage": by_stage,
        "active_projects": len([p for p in projects if p.stage != "Closed"]),
        "overdue": overdue_projects(session),
        "blocked_on_materials": blocked_projects(session),
        "capacity": capacity_ahead(session),
        "pending_approvals": len(queued),
        "note": ("Draft for approval queue — nothing is sent until a person "
                 "approves it (4.4)."),
    }
