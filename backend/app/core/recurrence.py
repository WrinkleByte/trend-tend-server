"""Canonical due-date/usage calculation for MaintenanceSchedule.

This module is the single source of truth for "when is this next due /
overdue" logic. The mobile app's KMP shared module (RecurrenceEngine.kt) must
stay behaviorally identical to this file — both are validated against the
same JSON test-vector fixtures (see tests/test_recurrence.py) so the two
independent implementations can't silently drift apart.
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ScheduleState:
    interval_type: str  # "time" | "usage" | "both"
    interval_days: int | None
    interval_usage_amount: int | None
    anchor_date: date | None
    anchor_usage_value: int | None


@dataclass(frozen=True)
class DueStatus:
    next_due_date: date | None
    next_due_usage: int | None
    is_overdue: bool


def compute_due_status(schedule: ScheduleState, *, today: date, current_usage: int | None) -> DueStatus:
    """`today` and `current_usage` are passed in explicitly (rather than read
    from a clock/asset lookup inside this function) so the calculation is a
    pure function — trivial to unit test and to port faithfully to Kotlin."""

    next_due_date: date | None = None
    if schedule.interval_type in ("time", "both") and schedule.anchor_date and schedule.interval_days:
        next_due_date = schedule.anchor_date + timedelta(days=schedule.interval_days)

    next_due_usage: int | None = None
    if (
        schedule.interval_type in ("usage", "both")
        and schedule.anchor_usage_value is not None
        and schedule.interval_usage_amount
    ):
        next_due_usage = schedule.anchor_usage_value + schedule.interval_usage_amount

    is_overdue = False
    if next_due_date is not None and today >= next_due_date:
        is_overdue = True
    if next_due_usage is not None and current_usage is not None and current_usage >= next_due_usage:
        is_overdue = True

    return DueStatus(next_due_date=next_due_date, next_due_usage=next_due_usage, is_overdue=is_overdue)
