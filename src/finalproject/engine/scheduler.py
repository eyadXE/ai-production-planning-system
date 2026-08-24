"""Scheduler — clause 3.1/3.2/3.3: whole-week booking with delay detection."""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class CapacityRow:
    week_label: str
    start_date: date
    free_hours: float


@dataclass
class ScheduleResult:
    start_week: str
    fab_end_week: str
    install_week_label: str
    planned_finish: date
    bookings: list[tuple[str, float]]      # (week_label, hours)
    galvanised: bool


def _sunday(week_start: date) -> date:
    return week_start + timedelta(days=6)


def _week_label(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def schedule(
    fab_hours: float,
    capacity: list[CapacityRow],
    galvanised: bool,
    host_min_free: float,
    topup_max: float,
    galv_weeks: int = 2,
) -> ScheduleResult:
    """Books the run into whole weeks per the platform policy (rates.py)."""
    weeks = sorted(capacity, key=lambda r: r.start_date)

    # extend the horizon with virtual fresh weeks beyond the file
    if weeks:
        last = weeks[-1].start_date
        for k in range(1, 13):
            start = last + timedelta(weeks=k)
            weeks.append(CapacityRow(_week_label(start), start, 320.0))

    remaining = fab_hours
    bookings: list[tuple[str, float]] = []
    started = False

    for row in weeks:
        if remaining <= 0.001:
            break
        free = max(row.free_hours, 0.0)
        if not started:
            # a fragmented week cannot host a fresh run (policy: rates.py)
            if free < host_min_free or free < min(remaining, host_min_free):
                continue
            take = min(free, remaining)
            bookings.append((row.week_label, round(take, 2)))
            started = True
            remaining -= take
        else:
            take = min(free, topup_max, remaining)
            if take <= 0:
                continue
            bookings.append((row.week_label, round(take, 2)))
            remaining -= take

    if not bookings:  # no capacity at all — degenerate fallback
        first = weeks[0]
        bookings.append((first.week_label, round(fab_hours, 2)))
        fab_end = first.start_date
    else:
        label0 = bookings[-1][0]
        y, w, _ = None, None, None
        for row in weeks:
            if row.week_label == label0:
                fab_end = row.start_date
                break
        else:
            y, w, _ = _parse_label(label0)
            fab_end = date.fromisocalendar(y, w, 1)

    # Clause 3.2 — the 2-week subcontract turnaround ends at the close of the
    # second week after fabrication; delivery + installation occupy the next.
    install_offset = (galv_weeks + 1) if galvanised else 1
    install_start = fab_end + timedelta(weeks=install_offset)
    planned_finish = _sunday(install_start)

    return ScheduleResult(
        start_week=bookings[0][0],
        fab_end_week=bookings[-1][0],
        install_week_label=_week_label(install_start),
        planned_finish=planned_finish,
        bookings=bookings,
        galvanised=galvanised,
    )


def _parse_label(label: str) -> tuple[int, int]:
    year, week = label.split("-W")
    return int(year), int(week)
