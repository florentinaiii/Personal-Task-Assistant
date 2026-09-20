import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional, Literal

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from models import TaskCreate
from parser import TaskParser, local_now


load_dotenv()

APP_TIMEZONE = ZoneInfo("Europe/Belgrade")
DEFAULT_REMINDER_MINUTES = 5


class LLMTask(BaseModel):
    title: str = Field(
        description=(
            "Short action-oriented task title. "
            "Example: 'Review my notes', not 'I need to review my notes'."
        )
    )

    deadline: Optional[str] = Field(
        default=None,
        description=(
            "Task deadline in ISO 8601 format YYYY-MM-DDTHH:MM:SS. "
            "Return null when no deadline can reasonably be determined."
        ),
    )

    priority: int = Field(
        default=1,
        ge=1,
        le=3,
        description="1 = low, 2 = medium, 3 = high.",
    )

    category: Optional[str] = Field(
        default=None,
        description=(
            "Short category such as Work, University, Personal, "
            "Health, Meeting, or Shopping."
        ),
    )

    estimated_duration: Optional[float] = Field(
        default=None,
        description="Estimated duration in hours if explicitly stated.",
    )

    is_recurring: bool = Field(
        default=False,
        description="Whether the task repeats.",
    )

    recurring_pattern: Optional[
        Literal["daily", "weekly", "monthly", "biweekly"]
    ] = Field(
        default=None,
        description="Recurring pattern, or null for a non-recurring task.",
    )

    reminder_requested: bool = Field(
        default=False,
        description=(
            "True when the user asks to be reminded or notified about "
            "this task, even if the wording contains a typo."
        ),
    )

    reminder_minutes_before: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Number of minutes before the deadline for a reminder. "
            "Only set this when the user explicitly specifies an interval "
            "before the deadline."
        ),
    )


class LLMTaskResult(BaseModel):
    is_task_request: bool = Field(
        description=(
            "True when the user is asking to create or remember "
            "one or more tasks."
        )
    )

    tasks: List[LLMTask] = Field(
        default_factory=list,
        description="Tasks extracted from the user's request.",
    )


class LLMTaskParser:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")

        self.client = (
            genai.Client(api_key=self.api_key)
            if self.api_key
            else None
        )

        # Existing deterministic parser is kept as fallback.
        self.fallback_parser = TaskParser()

    def is_available(self) -> bool:
        return self.client is not None

    def parse_task_from_text(
        self,
        text: str,
        user_email: Optional[str] = None,
    ) -> List[TaskCreate]:

        # If Gemini is unavailable, use the existing parser.
        if not self.client:
            print(
                "Gemini API key not found. "
                "Using deterministic parser."
            )
            return self.fallback_parser.parse_task_from_text(text)

        try:
            llm_tasks = self._parse_with_llm(text)

            # If Gemini returns no usable result, use fallback.
            if llm_tasks is None:
                return self.fallback_parser.parse_task_from_text(text)

            # The message is not a task-creation request.
            if not llm_tasks.is_task_request:
                return []

            converted_tasks = self._convert_tasks(
                llm_tasks.tasks,
                original_text=text,
                user_email=user_email,
            )

            if converted_tasks:
                print("Task interpreted with Gemini LLM.")
                return converted_tasks

            # Gemini successfully interpreted the request, but all
            # extracted tasks were rejected by application validation
            # (for example, because the deadline is in the past).
            # Do not use the fallback parser here, because it could
            # recreate a task that was intentionally rejected.
            print("Gemini task rejected by application validation.")
            return []

        except Exception as exc:
            print(
                f"Gemini LLM parsing failed: {exc}. "
                "Using deterministic parser."
            )

            return self.fallback_parser.parse_task_from_text(text)

    def _parse_with_llm(
        self,
        text: str,
    ) -> Optional[LLMTaskResult]:

        now = local_now()

        prompt = f"""
You are the natural-language task interpretation component
of a personal task management assistant.

CURRENT LOCAL DATE AND TIME:
{now.strftime("%Y-%m-%d %H:%M:%S")}

TIMEZONE:
Europe/Belgrade (Kosovo local time)

USER MESSAGE:
{text}

Extract tasks from the user's message.

Rules:

1. Do not invent a task if the message is not asking to create,
remember, schedule, or manage a task.

2. Produce short, clean, action-oriented titles.

Examples:
"I need to review my notes"
-> "Review my notes"

"Remind me to call my supervisor"
-> "Call my supervisor"

3. Resolve relative dates using the current local date/time.

Examples:
"tomorrow"
"next Monday"
"in two days"

IMPORTANT DATE FORMAT RULE:
Numeric dates written as DD.MM.YYYY, DD/MM/YYYY, or DD-MM-YYYY
must ALWAYS be interpreted as DAY-MONTH-YEAR, never MONTH-DAY-YEAR.

Examples:
12.02.2026 = February 12, 2026
03.04.2027 = April 3, 2027
25.12.2026 = December 25, 2026

4. Never silently move an explicitly requested past time to
another day.

If the user explicitly requests a time today that has already
passed, return that actual past datetime. The application will
validate and reject it.

5. Priority:
1 = normal/low
2 = important/medium
3 = urgent/high

Only increase priority when the wording supports it.

6. Recurrence:
every day -> daily
every week -> weekly
every two weeks -> biweekly
every month -> monthly

7. Do not invent an estimated duration.

8. Set reminder_requested=true when the user asks to be
reminded or notified about the task. Interpret this semantically
and tolerate obvious minor typos such as "remin me".

For reminder_minutes_before, only return a number when the user
explicitly specifies an interval BEFORE the deadline, such as
"10 minutes before" or "1 hour before".

Important:
"remind me in 5 minutes" means the task deadline is 5 minutes
from now. It does NOT mean reminder_minutes_before=5.
In that case set reminder_requested=true and
reminder_minutes_before=null. The application chooses a safe
reminder interval for near-term tasks.

If the user simply says "remind me" without specifying how long
before the deadline, set reminder_requested=true and
reminder_minutes_before=null.

Scheduled meetings are a special case:
When the user schedules an actual meeting with a deadline/time, use
category="Meeting". Meetings automatically receive an email reminder
from the application even when the user does not explicitly say
"remind me". If the user does not specify a reminder interval, leave
reminder_minutes_before=null; the application will default the meeting
reminder to 5 minutes before the meeting.

9. A single message may contain multiple tasks.

10. Preserve the user's intended meaning. Do not add actions
that were not requested.
"""

        interaction = self.client.interactions.create(
            model="gemini-3.1-flash-lite",
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": LLMTaskResult.model_json_schema(),
            },
        )

        if not interaction.output_text:
            return None

        return LLMTaskResult.model_validate_json(
            interaction.output_text
        )

    def _convert_tasks(
        self,
        tasks: List[LLMTask],
        original_text: str,
        user_email: Optional[str],
    ) -> List[TaskCreate]:

        converted: List[TaskCreate] = []
        now = local_now()
        normalized_text = original_text.lower()

        for item in tasks:
            title = item.title.strip()

            if not title:
                continue

            deadline = self._parse_datetime(
                item.deadline
            )

            # Reject deadlines that Gemini interpreted as past.
            if deadline is not None and deadline <= now:
                print(
                    f"Rejected past LLM deadline: {deadline}"
                )
                continue

            recurring_pattern = (
                item.recurring_pattern
                if item.is_recurring
                else None
            )

            # For recurring tasks without a first occurrence,
            # let the deterministic parser calculate it.
            if item.is_recurring and deadline is None:
                fallback_tasks = (
                    self.fallback_parser
                    .parse_task_from_text(original_text)
                )

                if fallback_tasks:
                    deadline = fallback_tasks[0].deadline

            is_scheduled_meeting = (
                (item.category or "").strip().lower() == "meeting"
                and deadline is not None
            )

            reminder_requested = (
                is_scheduled_meeting
                or item.reminder_requested
                or item.reminder_minutes_before is not None
                or "email" in normalized_text
                or "remind me" in normalized_text
            )

            notification_type = (
                "email"
                if reminder_requested
                else "websocket"
            )

            reminder_minutes_before = (
                item.reminder_minutes_before
            )

            # If a reminder was requested without an explicit
            # "X minutes before" interval, choose an adaptive default.
            #
            # Example:
            # - task due in 5 minutes -> remind 3 minutes before
            # - task due in 10+ minutes -> remind 5 minutes before
            if (
                reminder_requested
                and reminder_minutes_before is None
                and deadline is not None
            ):
                minutes_until_deadline = (
                    deadline - now
                ).total_seconds() / 60

                if is_scheduled_meeting:
                    # Meetings default to an email reminder 5 minutes
                    # before the scheduled start time. For a meeting
                    # created less than 5 minutes away, use a safe
                    # near-term reminder instead.
                    if minutes_until_deadline > DEFAULT_REMINDER_MINUTES:
                        reminder_minutes_before = (
                            DEFAULT_REMINDER_MINUTES
                        )
                    elif minutes_until_deadline <= 1:
                        reminder_minutes_before = 0
                    else:
                        reminder_minutes_before = max(
                            0,
                            int(minutes_until_deadline) - 1,
                        )
                elif minutes_until_deadline <= 1:
                    reminder_minutes_before = 0
                elif minutes_until_deadline < 10:
                    reminder_minutes_before = min(
                        3,
                        max(
                            0,
                            int(minutes_until_deadline) - 1,
                        ),
                    )
                else:
                    reminder_minutes_before = (
                        DEFAULT_REMINDER_MINUTES
                    )

            recipient_email = (
                user_email
                if notification_type == "email"
                else None
            )

            converted.append(
                TaskCreate(
                    title=title,
                    description=original_text,
                    deadline=deadline,
                    priority=item.priority,
                    category=item.category,
                    estimated_duration=item.estimated_duration,
                    notification_type=notification_type,
                    recipient_email=recipient_email,
                    reminder_minutes_before=(
                        reminder_minutes_before
                    ),
                    is_recurring=item.is_recurring,
                    recurring_pattern=recurring_pattern,
                )
            )

        return converted

    @staticmethod
    def _parse_datetime(
        value: Optional[str],
    ) -> Optional[datetime]:

        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            # Database deadlines are stored as naive Kosovo-local
            # datetimes. If Gemini returns an aware datetime,
            # convert it to the application timezone first and only
            # then remove tzinfo.
            if parsed.tzinfo is not None:
                parsed = (
                    parsed
                    .astimezone(APP_TIMEZONE)
                    .replace(tzinfo=None)
                )

            return parsed

        except (TypeError, ValueError):
            return None
