import logging
import calendar
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from models import Task

logger = logging.getLogger(__name__)


class RecurringTaskManager:
    def __init__(self):
        self.check_interval_hours = 1  # Check every hour

    def process_recurring_tasks(self, db: Session) -> List[Task]:
        """Process recurring tasks and create new instances when needed"""
        created_tasks = []

        recurring_tasks = db.query(Task).filter(
            Task.is_recurring == True,
            Task.status != "completed",
            Task.recurring_pattern.isnot(None)
        ).all()

        for task in recurring_tasks:
            new_task = self._create_next_instance(db, task)
            if new_task:
                created_tasks.append(new_task)
                logger.info(
                    f"Created recurring task instance: {new_task.title}"
                )

        return created_tasks

    def _create_next_instance(self, db: Session, parent_task: Task) -> Task:
        """Create the next future instance of a recurring task"""
        if not parent_task.deadline:
            logger.warning(
                f"Recurring task {parent_task.id} has no deadline, skipping"
            )
            return None

        pattern = parent_task.recurring_pattern.lower()
        now = datetime.now()

        next_deadline = self._calculate_next_deadline(
            parent_task.deadline,
            pattern,
            now
        )

        if not next_deadline:
            return None

        existing = db.query(Task).filter(
            Task.title == parent_task.title,
            Task.deadline == next_deadline,
            Task.user_id == parent_task.user_id
        ).first()

        if existing:
            return None

        new_task = Task(
            title=parent_task.title,
            description=parent_task.description,
            deadline=next_deadline,
            priority=parent_task.priority,
            estimated_duration=parent_task.estimated_duration,
            category=parent_task.category,
            notification_type=parent_task.notification_type,
            recipient_email=parent_task.recipient_email,
            reminder_minutes_before=parent_task.reminder_minutes_before,
            email_sent=False,
            user_id=parent_task.user_id,
            status="pending",
            is_recurring=False,
            recurring_pattern=None
        )

        db.add(new_task)
        db.commit()
        db.refresh(new_task)

        return new_task

    def _add_months(self, value: datetime, months: int = 1) -> datetime:
        """Add months safely, including dates such as January 31."""
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1

        max_day = calendar.monthrange(year, month)[1]
        day = min(value.day, max_day)

        return value.replace(
            year=year,
            month=month,
            day=day
        )

    def _calculate_next_deadline(
        self,
        last_deadline: datetime,
        pattern: str,
        now: datetime
    ) -> datetime:
        """
        Calculate the next recurring deadline.

        The deadline is advanced from the previous scheduled occurrence
        until it is strictly in the future. This prevents recurring tasks
        from being created immediately as overdue.
        """
        next_deadline = last_deadline

        while next_deadline <= now:
            if pattern == "daily":
                next_deadline += timedelta(days=1)

            elif pattern == "weekly":
                next_deadline += timedelta(weeks=1)

            elif pattern == "biweekly":
                next_deadline += timedelta(weeks=2)

            elif pattern == "monthly":
                next_deadline = self._add_months(
                    next_deadline,
                    1
                )

            else:
                logger.warning(
                    f"Unknown recurring pattern: {pattern}"
                )
                return None

        return next_deadline

    def mark_instance_completed(
        self,
        db: Session,
        task: Task
    ) -> bool:
        """Mark a recurring task instance as completed"""
        task.status = "completed"
        task.updated_at = datetime.now()
        db.commit()

        parent_task = db.query(Task).filter(
            Task.id == task.id,
            Task.is_recurring == True
        ).first()

        if parent_task:
            next_instance = self._create_next_instance(
                db,
                parent_task
            )

            if next_instance:
                logger.info(
                    "Created next recurring instance after completion: "
                    f"{next_instance.title}"
                )
                return True

        return False


recurring_task_manager = RecurringTaskManager()
