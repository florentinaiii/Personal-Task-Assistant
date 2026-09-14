import asyncio
import logging
import calendar

from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from models import Task


logger = logging.getLogger(__name__)


class RecurringTaskManager:
    def __init__(self):
        self.check_interval_hours = 1
        self.running = False

    # =========================================================
    # BACKGROUND PROCESS
    # =========================================================

    async def start_background_tasks(self, db_factory):
        """
        Continuously check recurring tasks.

        This keeps recurring schedules active even when
        the user does not manually complete a task.
        """

        if self.running:
            return

        self.running = True

        asyncio.create_task(
            self._background_loop(db_factory)
        )

    async def _background_loop(self, db_factory):
        while self.running:
            db = db_factory()

            try:
                self.process_recurring_tasks(db)

            except Exception as exc:
                logger.exception(
                    f"Error processing recurring tasks: {exc}"
                )

            finally:
                db.close()

            await asyncio.sleep(
                self.check_interval_hours * 60 * 60
            )

    # =========================================================
    # PROCESS RECURRING TASKS
    # =========================================================

    def process_recurring_tasks(
        self,
        db: Session,
    ) -> List[Task]:

        created_tasks = []

        recurring_tasks = (
            db.query(Task)
            .filter(
                Task.is_recurring == True,
                Task.status != "completed",
                Task.recurring_pattern.isnot(None),
            )
            .all()
        )

        for task in recurring_tasks:
            new_task = self._create_next_instance(
                db,
                task,
            )

            if new_task:
                created_tasks.append(new_task)

                logger.info(
                    "Created recurring task instance: "
                    f"{new_task.title} - "
                    f"{new_task.deadline}"
                )

        return created_tasks

    # =========================================================
    # CREATE NEXT INSTANCE
    # =========================================================

    def _create_next_instance(
        self,
        db: Session,
        parent_task: Task,
    ) -> Task:

        if not parent_task.deadline:
            logger.warning(
                f"Recurring task {parent_task.id} "
                "has no deadline, skipping"
            )

            return None

        pattern = (
            parent_task
            .recurring_pattern
            .lower()
        )

        now = datetime.now()

        next_deadline = (
            self._calculate_next_deadline(
                parent_task.deadline,
                pattern,
                now,
            )
        )

        if not next_deadline:
            return None

        # -----------------------------------------------------
        # CHECK DUPLICATES
        # -----------------------------------------------------

        existing = (
            db.query(Task)
            .filter(
                Task.title == parent_task.title,
                Task.deadline == next_deadline,
                Task.user_id == parent_task.user_id,
            )
            .first()
        )

        if existing:
            return None

        # -----------------------------------------------------
        # CREATE INSTANCE
        # -----------------------------------------------------

        new_task = Task(
            title=parent_task.title,
            description=parent_task.description,
            deadline=next_deadline,
            priority=parent_task.priority,
            estimated_duration=(
                parent_task.estimated_duration
            ),
            category=parent_task.category,
            notification_type=(
                parent_task.notification_type
            ),
            recipient_email=(
                parent_task.recipient_email
            ),
            reminder_minutes_before=(
                parent_task.reminder_minutes_before
            ),
            email_sent=False,
            user_id=parent_task.user_id,
            status="pending",

            # Child instance itself is not the template.
            is_recurring=False,
            recurring_pattern=None,
        )

        db.add(new_task)
        db.commit()
        db.refresh(new_task)

        return new_task

    # =========================================================
    # CALCULATE NEXT DEADLINE
    # =========================================================

    def _calculate_next_deadline(
        self,
        last_deadline: datetime,
        pattern: str,
        now: datetime,
    ) -> datetime:

        # Start from the NEXT occurrence,
        # not the current parent occurrence.
        if pattern == "daily":
            next_deadline = (
                last_deadline
                + timedelta(days=1)
            )

        elif pattern == "weekly":
            next_deadline = (
                last_deadline
                + timedelta(weeks=1)
            )

        elif pattern == "biweekly":
            next_deadline = (
                last_deadline
                + timedelta(weeks=2)
            )

        elif pattern == "monthly":
            next_deadline = self._add_months(
                last_deadline,
                1,
            )

        else:
            logger.warning(
                f"Unknown recurring pattern: {pattern}"
            )

            return None

        # -----------------------------------------------------
        # IF BACKEND WAS OFF FOR SOME TIME,
        # MOVE FORWARD UNTIL FUTURE
        # -----------------------------------------------------

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
                    1,
                )

        return next_deadline

    # =========================================================
    # MONTH CALCULATION
    # =========================================================

    def _add_months(
        self,
        value: datetime,
        months: int = 1,
    ) -> datetime:

        month_index = (
            value.month
            - 1
            + months
        )

        year = (
            value.year
            + month_index // 12
        )

        month = (
            month_index % 12
            + 1
        )

        max_day = calendar.monthrange(
            year,
            month,
        )[1]

        day = min(
            value.day,
            max_day,
        )

        return value.replace(
            year=year,
            month=month,
            day=day,
        )

    # =========================================================
    # COMPLETE TASK
    # =========================================================

    def mark_instance_completed(
        self,
        db: Session,
        task: Task,
    ) -> bool:

        task.status = "completed"
        task.updated_at = datetime.now()

        db.commit()

        # Do not stop the recurring schedule.
        # The parent recurring templates continue
        # creating future instances automatically.

        return True

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):
        self.running = False


recurring_task_manager = RecurringTaskManager()