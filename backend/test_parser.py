from datetime import datetime, timedelta

import pytest

from parser import TaskParser


@pytest.fixture
def parser():
    """Create a fresh TaskParser instance for each test."""
    return TaskParser()


def get_single_task(parser, text):
    """Parse text and ensure exactly one task is returned."""
    tasks = parser.parse_task_from_text(text)

    assert tasks, f"No task was parsed for: {text}"
    assert len(tasks) == 1, (
        f"Expected 1 task for '{text}', but got {len(tasks)}"
    )

    return tasks[0]


def test_time_5pm(parser):
    task = get_single_task(parser, "Remind me to send a project in 2 days at 5pm")
    assert task.deadline is not None
    assert task.deadline.hour == 17
    assert task.deadline.minute == 0


def test_tomorrow_at_4pm(parser):
    task = get_single_task(parser, "remind me to send an email tomorrow at 4pm")
    expected_date = (datetime.now() + timedelta(days=1)).date()
    assert task.deadline is not None
    assert task.deadline.date() == expected_date
    assert task.deadline.hour == 16
    assert task.deadline.minute == 0


def test_tomorrow_at_5pm(parser):
    task = get_single_task(parser, "remind me to attend a meeting tomorrow at 5pm")
    expected_date = (datetime.now() + timedelta(days=1)).date()
    assert task.deadline is not None
    assert task.deadline.date() == expected_date
    assert task.deadline.hour == 17
    assert task.deadline.minute == 0


def test_tomorrow_at_5_00pm(parser):
    task = get_single_task(parser, "remind me to attend a meeting tomorrow at 5:00pm")
    expected_date = (datetime.now() + timedelta(days=1)).date()
    assert task.deadline is not None
    assert task.deadline.date() == expected_date
    assert task.deadline.hour == 17
    assert task.deadline.minute == 0


def test_reject_past_time_today(parser, monkeypatch):
    """Reject an explicitly requested time that has already passed today."""
    fixed_now = datetime(2026, 9, 20, 12, 0, 0)
    monkeypatch.setattr("parser.local_now", lambda: fixed_now)

    tasks = parser.parse_task_from_text(
        "remind me to attend a meeting today at 8am"
    )

    assert tasks == []


def test_in_2_days_at_6pm(parser):
    task = get_single_task(parser, "remind me to attend a meeting in 2 days at 6pm")
    expected_date = (datetime.now() + timedelta(days=2)).date()
    assert task.deadline is not None
    assert task.deadline.date() == expected_date
    assert task.deadline.hour == 18
    assert task.deadline.minute == 0


def test_5_30pm(parser):
    task = get_single_task(parser, "remind me to send an email at 5:30pm")
    assert task.deadline is not None
    assert task.deadline.hour == 17
    assert task.deadline.minute == 30


def test_3pm(parser):
    task = get_single_task(parser, "remind me to call john at 3pm")
    assert task.deadline is not None
    assert task.deadline.hour == 15
    assert task.deadline.minute == 0


def test_recurring_weekly_task_title(parser):
    task = get_single_task(parser, "Every week I need to review my notes")
    assert task.title.lower() == "review my notes"


def test_recurring_weekly_task_is_future(parser):
    task = get_single_task(parser, "Every week I need to review my notes")
    assert task.deadline is not None
    assert task.deadline > datetime.now()
