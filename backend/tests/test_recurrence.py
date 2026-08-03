from datetime import date

from app.core.recurrence import ScheduleState, compute_due_status


def test_time_based_schedule_not_yet_due():
    schedule = ScheduleState(
        interval_type="time",
        interval_days=180,
        interval_usage_amount=None,
        anchor_date=date(2026, 1, 1),
        anchor_usage_value=None,
    )
    status = compute_due_status(schedule, today=date(2026, 3, 1), current_usage=None)
    assert status.next_due_date == date(2026, 6, 30)
    assert status.is_overdue is False


def test_time_based_schedule_overdue():
    schedule = ScheduleState(
        interval_type="time",
        interval_days=180,
        interval_usage_amount=None,
        anchor_date=date(2026, 1, 1),
        anchor_usage_value=None,
    )
    status = compute_due_status(schedule, today=date(2026, 7, 1), current_usage=None)
    assert status.is_overdue is True


def test_usage_based_schedule_overdue_by_mileage():
    schedule = ScheduleState(
        interval_type="usage",
        interval_days=None,
        interval_usage_amount=5000,
        anchor_date=None,
        anchor_usage_value=40000,
    )
    status = compute_due_status(schedule, today=date(2026, 1, 1), current_usage=46000)
    assert status.next_due_usage == 45000
    assert status.is_overdue is True


def test_both_interval_type_overdue_if_either_condition_met():
    schedule = ScheduleState(
        interval_type="both",
        interval_days=180,
        interval_usage_amount=5000,
        anchor_date=date(2026, 1, 1),
        anchor_usage_value=40000,
    )
    # Not overdue by date, but overdue by mileage
    status = compute_due_status(schedule, today=date(2026, 2, 1), current_usage=46000)
    assert status.is_overdue is True


def test_not_overdue_when_neither_condition_met():
    schedule = ScheduleState(
        interval_type="both",
        interval_days=180,
        interval_usage_amount=5000,
        anchor_date=date(2026, 1, 1),
        anchor_usage_value=40000,
    )
    status = compute_due_status(schedule, today=date(2026, 2, 1), current_usage=41000)
    assert status.is_overdue is False
