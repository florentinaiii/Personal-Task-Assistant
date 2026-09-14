import re
from datetime import datetime, timedelta
from typing import List, Optional

from dateutil import parser as date_parser

from models import TaskCreate


class TaskParser:
    def __init__(self):
        self.priority_keywords = {
            "urgent": 3,
            "asap": 3,
            "immediately": 3,
            "critical": 3,
            "very important": 3,
            "extremely important": 3,
            "as soon as possible": 3,
            "important": 2,
            "high": 2,
            "soon": 2,
            "low": 1,
            "later": 1,
            "sometime": 1,
        }

        self.recurring_patterns = {
            "daily": [
                "every day this week",
                "every day",
                "daily",
                "each day",
                "per day",
                "times a day",
            ],
            "weekly": [
                "every week",
                "weekly",
                "each week",
            ],
            "monthly": [
                "every month",
                "monthly",
                "each month",
            ],
            "biweekly": [
                "every two weeks",
                "biweekly",
                "every other week",
            ],
        }

        self.common_misspellings = {
            "sen": "send",
            "reming": "remind",
            "wich": "which",
            "sendd": "send",
            "remindd": "remind",
            "tommorrow": "tomorrow",
            "tody": "today",
            "oclock": "o'clock",
            "minitues": "minutes",
            "meet": "meeting",
        }

    # =========================================================
    # NORMALIZE
    # =========================================================

    def normalize_text(self, text: str) -> str:
        normalized = text.lower().strip()

        for wrong, correct in self.common_misspellings.items():
            normalized = re.sub(
                rf"\b{re.escape(wrong)}\b",
                correct,
                normalized,
            )

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        ).strip()

        return normalized

    # =========================================================
    # MAIN PARSER
    # =========================================================

    def parse_task_from_text(self, text: str) -> List[TaskCreate]:
        normalized_text = self.normalize_text(text)

        # -----------------------------------------------------
        # EVERY DAY THIS WEEK
        # -----------------------------------------------------

        if "every day this week" in normalized_text:
            tasks = self._create_tasks_for_this_week(
                normalized_text,
                text,
            )

            if tasks:
                return tasks

        # -----------------------------------------------------
        # MULTIPLE TIMES IN ONE REQUEST
        # -----------------------------------------------------

        multiple_time_tasks = self._create_tasks_for_multiple_times(
            normalized_text,
            text,
        )

        if multiple_time_tasks:
            return multiple_time_tasks

        # -----------------------------------------------------
        # IN X MINUTES
        # -----------------------------------------------------

        in_minutes_match = re.search(
            r"\bin\s+(\d+)\s*minutes?\b",
            normalized_text,
            re.IGNORECASE,
        )

        if in_minutes_match:
            task = self._extract_single_task(
                normalized_text,
                text,
            )

            if task:
                minutes = int(in_minutes_match.group(1))

                task.deadline = (
                    datetime.now()
                    + timedelta(minutes=minutes)
                )

                if minutes <= 2:
                    task.reminder_minutes_before = 1

                elif minutes <= 5:
                    task.reminder_minutes_before = minutes - 1

                else:
                    task.reminder_minutes_before = min(
                        5,
                        minutes - 1,
                    )

                task.notification_type = "email"

            return [task] if task else []

        # -----------------------------------------------------
        # NORMAL SINGLE TASK
        # -----------------------------------------------------

        if any(
            phrase in normalized_text
            for phrase in [
                "remind me",
                "before",
                "after",
                "at",
                "by",
                "email me",
                "send me an email",
                "today",
                "tomorrow",
            ]
        ):
            task = self._extract_single_task(
                normalized_text,
                text,
            )

            return [task] if task else []

        # -----------------------------------------------------
        # MULTIPLE SEPARATE TASKS
        # -----------------------------------------------------

        task_segments = re.split(
            r";|\band\b|\balso\b|\bplus\b",
            normalized_text,
            flags=re.IGNORECASE,
        )

        tasks = []

        for segment in task_segments:
            segment = segment.strip()

            if len(segment) < 3:
                continue

            task = self._extract_single_task(
                segment,
                text,
            )

            if task:
                tasks.append(task)

        return tasks

    # =========================================================
    # MULTIPLE TIMES
    # =========================================================

    def _create_tasks_for_multiple_times(
        self,
        normalized_text: str,
        original_text: str,
    ) -> List[TaskCreate]:

        time_pattern = (
            r"\b(1[0-2]|0?[1-9])"
            r"(?::([0-5]\d))?"
            r"\s*(am|pm)\b"
        )

        matches = list(
            re.finditer(
                time_pattern,
                normalized_text,
                re.IGNORECASE,
            )
        )

        if len(matches) < 2:
            return []

        times = []

        for match in matches:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            meridiem = match.group(3).lower()

            if meridiem == "pm" and hour != 12:
                hour += 12

            elif meridiem == "am" and hour == 12:
                hour = 0

            time_value = (hour, minute)

            if time_value not in times:
                times.append(time_value)

        if len(times) < 2:
            return []

        recurring_pattern = self._extract_recurring_pattern(
            normalized_text
        )

        if re.search(
            r"\b\d+\s+times?\s+"
            r"(?:per\s+day|a\s+day|each\s+day|daily)\b",
            normalized_text,
            re.IGNORECASE,
        ):
            recurring_pattern = "daily"

        is_recurring = recurring_pattern is not None

        # -----------------------------------------------------
        # CLEAN ACTION / TITLE
        # -----------------------------------------------------

        action_text = re.sub(
            time_pattern,
            " ",
            normalized_text,
            flags=re.IGNORECASE,
        )

        instruction_patterns = [
            r"\bremind me to\b",
            r"\bremember to\b",
            r"\bdon't forget to\b",
            r"\bi need to\b",
            r"\bneed to\b",
            r"\bi have to\b",
            r"\bhave to\b",
            r"\bi should\b",
            r"\bshould\b",
        ]

        for pattern in instruction_patterns:
            action_text = re.sub(
                pattern,
                " ",
                action_text,
                flags=re.IGNORECASE,
            )

        action_text = re.sub(
            r"\b\d+\s+times?\s+"
            r"(?:per\s+day|a\s+day|each\s+day|daily)\b",
            " ",
            action_text,
            flags=re.IGNORECASE,
        )

        recurrence_cleanup_patterns = [
            r"\bevery\s+day\b",
            r"\beach\s+day\b",
            r"\bdaily\b",
            r"\bevery\s+week\b",
            r"\beach\s+week\b",
            r"\bweekly\b",
            r"\bevery\s+month\b",
            r"\beach\s+month\b",
            r"\bmonthly\b",
            r"\bevery\s+other\s+week\b",
            r"\bevery\s+two\s+weeks\b",
            r"\bbiweekly\b",
        ]

        for pattern in recurrence_cleanup_patterns:
            action_text = re.sub(
                pattern,
                " ",
                action_text,
                flags=re.IGNORECASE,
            )

        # "pray, send a reminder..."
        action_text = re.sub(
            r",?\s*"
            r"(?:and\s+)?"
            r"(?:send\s+)?"
            r"(?:me\s+)?"
            r"(?:a\s+)?"
            r"(?:reminder|notification)"
            r".*$",
            " ",
            action_text,
            flags=re.IGNORECASE,
        )

        action_text = re.sub(
            r",?\s*"
            r"(?:and\s+)?"
            r"(?:email|notify)\s+me"
            r".*$",
            " ",
            action_text,
            flags=re.IGNORECASE,
        )

        action_text = re.sub(
            r"\b(?:at|by)\b",
            " ",
            action_text,
            flags=re.IGNORECASE,
        )

        action_text = re.sub(
            r"\s+",
            " ",
            action_text,
        ).strip(" ,.-?!:;")

        title = self._clean_title(action_text)

        if not title:
            title = "Reminder"

        priority = self._extract_priority(
            normalized_text
        )

        duration = self._extract_duration(
            normalized_text
        )

        notification_type = self._extract_notification_type(
            original_text
        )

        recipient_email = self._extract_email_address(
            original_text
        )

        now = datetime.now()

        tasks: List[TaskCreate] = []

        # -----------------------------------------------------
        # IF USER SPECIFICALLY SAID "TODAY"
        # -----------------------------------------------------
        #
        # Do not move passed times silently to tomorrow.
        #

        explicitly_today = (
            "today" in normalized_text
        )

        for hour, minute in times:
            deadline = now.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

            if deadline <= now:
                if explicitly_today:
                    # Skip passed times explicitly requested for today.
                    continue

                deadline += timedelta(days=1)

            reminder_minutes_before = (
                self._extract_reminder_minutes_before(
                    original_text,
                    deadline,
                )
            )

            tasks.append(
                TaskCreate(
                    title=title,
                    description=original_text,
                    deadline=deadline,
                    priority=priority,
                    estimated_duration=duration,
                    notification_type=notification_type,
                    recipient_email=recipient_email,
                    reminder_minutes_before=reminder_minutes_before,
                    is_recurring=is_recurring,
                    recurring_pattern=recurring_pattern,
                )
            )

        return tasks

    # =========================================================
    # EVERY DAY THIS WEEK
    # =========================================================

    def _create_tasks_for_this_week(
        self,
        normalized_text: str,
        original_text: str,
    ) -> List[TaskCreate]:

        template = self._extract_single_task(
            normalized_text,
            original_text,
        )

        if not template:
            return []

        now = datetime.now()

        time_match = re.search(
            r"\b(1[0-2]|0?[1-9])"
            r"(?::([0-5]\d))?"
            r"\s*(am|pm)\b",
            normalized_text,
            re.IGNORECASE,
        )

        if time_match:
            hour = int(time_match.group(1))
            minute = int(
                time_match.group(2) or 0
            )

            meridiem = (
                time_match.group(3).lower()
            )

            if meridiem == "pm" and hour != 12:
                hour += 12

            elif meridiem == "am" and hour == 12:
                hour = 0

        elif template.deadline:
            hour = template.deadline.hour
            minute = template.deadline.minute

        else:
            hour = 23
            minute = 59

        days_until_sunday = (
            6 - now.weekday()
        )

        week_end = (
            now
            + timedelta(days=days_until_sunday)
        ).date()

        first_candidate = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

        if first_candidate <= now:
            first_candidate += timedelta(days=1)

        if first_candidate.date() > week_end:
            days_until_next_monday = (
                7 - now.weekday()
            )

            next_monday = (
                now
                + timedelta(
                    days=days_until_next_monday
                )
            ).date()

            first_candidate = datetime.combine(
                next_monday,
                datetime.min.time(),
            ).replace(
                hour=hour,
                minute=minute,
            )

            week_end = (
                next_monday
                + timedelta(days=6)
            )

        tasks: List[TaskCreate] = []

        current = first_candidate

        while current.date() <= week_end:
            tasks.append(
                TaskCreate(
                    title=template.title,
                    description=original_text,
                    deadline=current,
                    priority=template.priority,
                    category=template.category,
                    estimated_duration=template.estimated_duration,
                    notification_type=template.notification_type,
                    recipient_email=template.recipient_email,
                    reminder_minutes_before=template.reminder_minutes_before,
                    is_recurring=False,
                    recurring_pattern=None,
                )
            )

            current += timedelta(days=1)

        return tasks

    # =========================================================
    # SINGLE TASK
    # =========================================================

    def _extract_single_task(
        self,
        text: str,
        original_text: Optional[str] = None,
    ) -> Optional[TaskCreate]:

        if original_text is None:
            original_text = text

        cleaned = re.sub(
            r"\b("
            r"remind me to|"
            r"remember to|"
            r"don't forget to|"
            r"need to|"
            r"have to|"
            r"should"
            r")\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        if not cleaned:
            return None

        # -----------------------------------------------------
        # IN X MINUTES
        # -----------------------------------------------------

        in_minutes_match = re.search(
            r"\bin\s+(\d+)\s*minutes?\b",
            self.normalize_text(original_text),
            re.IGNORECASE,
        )

        if in_minutes_match:
            main_action = re.sub(
                r"\bin\s+\d+\s*minutes?\b",
                "",
                original_text,
                flags=re.IGNORECASE,
            ).strip()

            cleaned = re.sub(
                r"\b("
                r"remind me to|"
                r"remember to|"
                r"don't forget to|"
                r"need to|"
                r"have to|"
                r"should"
                r")\b",
                "",
                main_action,
                flags=re.IGNORECASE,
            ).strip()

            minutes = int(
                in_minutes_match.group(1)
            )

            deadline = (
                datetime.now()
                + timedelta(minutes=minutes)
            )

            priority = self._extract_priority(
                cleaned
            )

            duration = self._extract_duration(
                cleaned
            )

            title = self._clean_title(
                cleaned
            )

            if minutes <= 2:
                reminder_minutes_before = 1

            elif minutes <= 5:
                reminder_minutes_before = minutes - 1

            else:
                reminder_minutes_before = min(
                    5,
                    minutes - 1,
                )

            notification_type = "email"

            recipient_email = (
                self._extract_email_address(
                    original_text
                )
            )

            recurring_pattern = (
                self._extract_recurring_pattern(
                    original_text
                )
            )

            is_recurring = (
                recurring_pattern is not None
            )

            if not title:
                return None

            return TaskCreate(
                title=title,
                description=cleaned,
                deadline=deadline,
                priority=priority,
                estimated_duration=duration,
                notification_type=notification_type,
                recipient_email=recipient_email,
                reminder_minutes_before=reminder_minutes_before,
                is_recurring=is_recurring,
                recurring_pattern=recurring_pattern,
            )

        # -----------------------------------------------------
        # NORMAL TASK
        # -----------------------------------------------------

        recurring_pattern = (
            self._extract_recurring_pattern(
                text
            )
        )

        is_recurring = (
            recurring_pattern is not None
        )

        deadline = self._extract_deadline(
            cleaned
        )

        # -----------------------------------------------------
        # "TODAY AT X" AND X HAS PASSED
        # -----------------------------------------------------

        if (
            "today" in cleaned.lower()
            and deadline is None
            and re.search(
                r"\b(1[0-2]|0?[1-9])"
                r"(?::([0-5]\d))?"
                r"\s*(am|pm)\b",
                cleaned,
                re.IGNORECASE,
            )
        ):
            return None

        # -----------------------------------------------------
        # RECURRING START DATE
        # -----------------------------------------------------

        if (
            is_recurring
            and (
                deadline is None
                or deadline <= datetime.now()
            )
        ):
            deadline = (
                self._calculate_initial_recurring_deadline(
                    text=text,
                    pattern=recurring_pattern,
                    parsed_deadline=deadline,
                )
            )

        priority = self._extract_priority(
            cleaned
        )

        duration = self._extract_duration(
            cleaned
        )

        title = self._clean_title(
            cleaned
        )

        notification_type = (
            self._extract_notification_type(
                text
            )
        )

        recipient_email = (
            self._extract_email_address(
                text
            )
        )

        reminder_minutes_before = (
            self._extract_reminder_minutes_before(
                text,
                deadline,
            )
        )

        if not title:
            return None

        return TaskCreate(
            title=title,
            description=original_text,
            deadline=deadline,
            priority=priority,
            estimated_duration=duration,
            notification_type=notification_type,
            recipient_email=recipient_email,
            reminder_minutes_before=reminder_minutes_before,
            is_recurring=is_recurring,
            recurring_pattern=recurring_pattern,
        )

    # =========================================================
    # DEADLINE
    # =========================================================

    def _extract_deadline(
        self,
        text: str,
    ) -> Optional[datetime]:

        now = datetime.now()

        def extract_explicit_time(value: str):
            match = re.search(
                r"\b(1[0-2]|0?[1-9])"
                r"(?::([0-5]\d))?"
                r"\s*(am|pm)\b",
                value,
                re.IGNORECASE,
            )

            if not match:
                return None

            hour = int(match.group(1))
            minute = int(
                match.group(2) or 0
            )

            meridiem = (
                match.group(3).lower()
            )

            if (
                meridiem == "pm"
                and hour != 12
            ):
                hour += 12

            elif (
                meridiem == "am"
                and hour == 12
            ):
                hour = 0

            return hour, minute

        explicit_time = (
            extract_explicit_time(text)
        )

        # -----------------------------------------------------
        # IN X MINUTES
        # -----------------------------------------------------

        match = re.search(
            r"\bin (\d+)\s*minutes?\b",
            text,
            re.IGNORECASE,
        )

        if match:
            return (
                now
                + timedelta(
                    minutes=int(match.group(1))
                )
            )

        # -----------------------------------------------------
        # IN X HOURS
        # -----------------------------------------------------

        match = re.search(
            r"\bin (\d+)\s*hours?\b",
            text,
            re.IGNORECASE,
        )

        if match:
            return (
                now
                + timedelta(
                    hours=int(match.group(1))
                )
            )

        # -----------------------------------------------------
        # IN X DAYS
        # -----------------------------------------------------

        match = re.search(
            r"\bin (\d+)\s*days?\b",
            text,
            re.IGNORECASE,
        )

        if match:
            base_date = (
                now
                + timedelta(
                    days=int(match.group(1))
                )
            )

            if explicit_time:
                hour, minute = explicit_time

                return base_date.replace(
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )

            return base_date.replace(
                hour=23,
                minute=59,
                second=0,
                microsecond=0,
            )

        # -----------------------------------------------------
        # TOMORROW
        # -----------------------------------------------------

        if "tomorrow" in text.lower():
            base_date = (
                now + timedelta(days=1)
            )

            if explicit_time:
                hour, minute = explicit_time

                return base_date.replace(
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )

            return base_date.replace(
                hour=23,
                minute=59,
                second=0,
                microsecond=0,
            )

        # -----------------------------------------------------
        # TODAY
        # -----------------------------------------------------

        if "today" in text.lower():
            if explicit_time:
                hour, minute = explicit_time

                candidate = now.replace(
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )

                # User explicitly requested today.
                # If that time passed, return None.
                if candidate <= now:
                    return None

                return candidate

            return now.replace(
                hour=23,
                minute=59,
                second=0,
                microsecond=0,
            )

        # -----------------------------------------------------
        # EXPLICIT TIME WITHOUT "TODAY"
        # -----------------------------------------------------

        if (
            explicit_time
            and any(
                word in text.lower()
                for word in [
                    "at",
                    "by",
                    "before",
                ]
            )
        ):
            hour, minute = explicit_time

            candidate = now.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

            # No explicit "today":
            # use next occurrence if time passed.
            if candidate <= now:
                candidate += timedelta(days=1)

            return candidate

        # -----------------------------------------------------
        # EXPLICIT DATES
        # -----------------------------------------------------

        patterns = [
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}-\d{1,2}-\d{4})",
            r"(next \w+)",
            r"(\w+ \d{1,2})",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:
                try:
                    parsed_date = (
                        date_parser.parse(
                            match.group(1),
                            fuzzy=True,
                        )
                    )

                    if explicit_time:
                        hour, minute = explicit_time

                        parsed_date = (
                            parsed_date.replace(
                                hour=hour,
                                minute=minute,
                                second=0,
                                microsecond=0,
                            )
                        )

                    elif (
                        parsed_date.time()
                        == datetime.min.time()
                    ):
                        parsed_date = (
                            parsed_date.replace(
                                hour=23,
                                minute=59,
                            )
                        )

                    return parsed_date

                except Exception:
                    continue

        return None

    # =========================================================
    # INITIAL RECURRING DEADLINE
    # =========================================================

    def _calculate_initial_recurring_deadline(
        self,
        text: str,
        pattern: str,
        parsed_deadline: Optional[datetime] = None,
    ) -> datetime:

        now = datetime.now()

        time_match = re.search(
            r"\b(1[0-2]|0?[1-9])"
            r"(?::([0-5]\d))?"
            r"\s*(am|pm)\b",
            text,
            re.IGNORECASE,
        )

        if time_match:
            hour = int(
                time_match.group(1)
            )

            minute = int(
                time_match.group(2) or 0
            )

            meridiem = (
                time_match.group(3).lower()
            )

            if (
                meridiem == "pm"
                and hour != 12
            ):
                hour += 12

            elif (
                meridiem == "am"
                and hour == 12
            ):
                hour = 0

        elif parsed_deadline:
            hour = parsed_deadline.hour
            minute = parsed_deadline.minute

        else:
            hour = 23
            minute = 59

        if pattern == "daily":
            candidate = now.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

            if candidate <= now:
                candidate += timedelta(days=1)

            return candidate

        if pattern == "weekly":
            return (
                now
                + timedelta(weeks=1)
            ).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        if pattern == "biweekly":
            return (
                now
                + timedelta(weeks=2)
            ).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        if pattern == "monthly":
            import calendar

            year = now.year
            month = now.month + 1

            if month == 13:
                year += 1
                month = 1

            max_day = calendar.monthrange(
                year,
                month,
            )[1]

            day = min(
                now.day,
                max_day,
            )

            return now.replace(
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        return (
            now
            + timedelta(days=1)
        ).replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

    # =========================================================
    # PRIORITY
    # =========================================================

    def _extract_priority(
        self,
        text: str,
    ) -> int:

        strong_phrases = {
            "very important": 3,
            "extremely important": 3,
            "as soon as possible": 3,
        }

        for phrase, value in strong_phrases.items():
            if phrase in text:
                return value

        for keyword, value in self.priority_keywords.items():
            if keyword in text:
                return value

        return 1

    # =========================================================
    # DURATION
    # =========================================================

    def _extract_duration(
        self,
        text: str,
    ) -> Optional[float]:

        patterns = [
            r"(\d+) hours?",
            r"(\d+) hrs?",
            r"(\d+) h\b",
            r"(\d+) minutes?",
            r"(\d+) mins?",
            r"(\d+) min\b",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:
                value = int(match.group(1))

                if any(
                    value_type in pattern
                    for value_type in [
                        "hour",
                        "hr",
                        " h",
                    ]
                ):
                    return float(value)

                return value / 60.0

        return None

    # =========================================================
    # CLEAN TITLE
    # =========================================================

    def _clean_title(
        self,
        text: str,
    ) -> str:

        cleaned = text.strip()

        if not cleaned:
            return ""

        instruction_patterns = [
            r"^\s*please\s+",
            r"^\s*can you\s+",
            r"^\s*could you\s+",
            r"^\s*would you\s+",
            r"^\s*i want you to\s+",
            r"^\s*i would like you to\s+",
            r"^\s*i'd like you to\s+",
            r"^\s*remind me to\s+",
            r"^\s*remember to\s+",
            r"^\s*don't forget to\s+",
            r"^\s*i need to\s+",
            r"^\s*need to\s+",
            r"^\s*i have to\s+",
            r"^\s*have to\s+",
            r"^\s*i should\s+",
            r"^\s*should\s+",
            r"^\s*add a task to\s+",
            r"^\s*add task to\s+",
            r"^\s*create a task to\s+",
            r"^\s*create task to\s+",
            r"^\s*add\s+",
            r"^\s*create\s+",
            r"^\s*plan to\s+",
        ]

        for pattern in instruction_patterns:
            cleaned = re.sub(
                pattern, "", cleaned, flags=re.IGNORECASE
            ).strip()

        priority_phrase_patterns = [
            (
                r",?\s*(?:it\s+is|it's|this\s+is)\s+"
                r"(?:very\s+|extremely\s+)?"
                r"(?:urgent|important|critical|high\s+priority|low\s+priority)\b"
            ),
            (
                r",?\s*(?:and\s+)?(?:make|mark|set)\s+(?:it\s+)?"
                r"(?:as\s+)?(?:urgent|important|critical|"
                r"high\s+priority|low\s+priority)\b"
            ),
        ]

        for pattern in priority_phrase_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        recurring_cleanup_patterns = [
            r"\bevery\s+day\s+this\s+week\b",
            r"\bevery\s+other\s+week\b",
            r"\bevery\s+two\s+weeks\b",
            r"\bevery\s+2\s+weeks\b",
            r"\bevery\s+day\b",
            r"\beach\s+day\b",
            r"\bdaily\b",
            r"\bevery\s+week\b",
            r"\beach\s+week\b",
            r"\bweekly\b",
            r"\bbiweekly\b",
            r"\bevery\s+month\b",
            r"\beach\s+month\b",
            r"\bmonthly\b",
            r"\b\d+\s+times?\s+per\s+day\b",
            r"\b\d+\s+times?\s+a\s+day\b",
            r"\b\d+\s+times?\s+each\s+day\b",
            r"\b\d+\s+times?\s+daily\b",
        ]

        for pattern in recurring_cleanup_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        reminder_patterns = [
            r",?\s*(?:and\s+)?remind me\s+\d+\s*minutes?\s+before.*$",
            r",?\s*(?:and\s+)?remind me\s+\d+\s*hours?\s+before.*$",
            r",?\s*(?:and\s+)?remind me\s+before\s+"
            r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?.*$",
            r",?\s*(?:and\s+)?remind me\s+at\s+"
            r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?.*$",
            r",?\s*(?:and\s+)?send me an email\b.*$",
            r",?\s*(?:and\s+)?email me\b.*$",
            r",?\s*(?:and\s+)?send\s+(?:me\s+)?(?:a\s+)?reminder\b.*$",
            r",?\s*(?:and\s+)?send\s+(?:me\s+)?(?:a\s+)?notification\b.*$",
            r",?\s*(?:and\s+)?notify me\b.*$",
        ]

        for pattern in reminder_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        date_patterns = [
            r"\bthis\s+morning\b",
            r"\bthis\s+afternoon\b",
            r"\bthis\s+evening\b",
            r"\btomorrow\s+morning\b",
            r"\btomorrow\s+afternoon\b",
            r"\btomorrow\s+evening\b",
            r"\btoday\b",
            r"\btomorrow\b",
            r"\btonight\b",
            r"\bnext\s+week\b",
            r"\bnext\s+month\b",
            r"\bnext\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\bthis\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\bon\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\bin\s+\d+\s*(?:days?|hours?|minutes?)\b",
        ]

        for pattern in date_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        explicit_date_patterns = [
            r"\bon\s+\w+\s+\d{1,2}(?:st|nd|rd|th)?\b",
            r"\b\w+\s+\d{1,2}(?:st|nd|rd|th)?\b",
            r"\bon\s+\d{1,2}/\d{1,2}/\d{2,4}\b",
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
            r"\bon\s+\d{1,2}-\d{1,2}-\d{2,4}\b",
            r"\b\d{1,2}-\d{1,2}-\d{2,4}\b",
        ]

        for pattern in explicit_date_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        time_patterns = [
            (
                r"\b(?:at|by|before|around)\s+"
                r"(?:1[0-2]|0?[1-9])(?::[0-5]\d)?\s*(?:am|pm)\b"
            ),
            r"\b(?:1[0-2]|0?[1-9])(?::[0-5]\d)?\s*(?:am|pm)\b",
            r"\bat\s+\d{1,2}:\d{2}\b",
            r"\bby\s+\d{1,2}:\d{2}\b",
        ]

        for pattern in time_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        duration_patterns = [
            r"\bfor\s+\d+(?:\.\d+)?\s*hours?\b",
            r"\bfor\s+\d+(?:\.\d+)?\s*hrs?\b",
            r"\bfor\s+\d+\s*minutes?\b",
            r"\bfor\s+\d+\s*mins?\b",
        ]

        for pattern in duration_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        for word in sorted(
            self.priority_keywords.keys(),
            key=len,
            reverse=True,
        ):
            cleaned = re.sub(
                rf"\b{re.escape(word)}\b",
                " ",
                cleaned,
                flags=re.IGNORECASE,
            )

        cleaned = re.sub(
            r"^\s*(?:to)\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s+(?:at|by|on|before)\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
        cleaned = re.sub(r"([,.!?;:]){2,}", r"\1", cleaned)
        cleaned = cleaned.strip(" ,.-?!:;")

        # Natural title normalization.
        meeting_match = re.fullmatch(
            r"(?:schedule|arrange|set\s+up|plan)\s+"
            r"(?:a\s+|an\s+|the\s+)?"
            r"(?:meeting|call)\s+with\s+"
            r"(?:the\s+)?(.+)",
            cleaned,
            flags=re.IGNORECASE,
        )

        if meeting_match:
            participant = meeting_match.group(1).strip()

            if participant.lower() == "team":
                cleaned = "Team meeting"
            else:
                cleaned = f"Meeting with {participant}"
        else:
            appointment_match = re.fullmatch(
                r"(?:schedule|arrange|set\s+up|book)\s+"
                r"(?:a\s+|an\s+|the\s+)?"
                r"(.+?\s+appointment)",
                cleaned,
                flags=re.IGNORECASE,
            )

            if appointment_match:
                cleaned = appointment_match.group(1).strip()

        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-?!:;")

        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        return cleaned

    # =========================================================
    # NOTIFICATION TYPE
    # =========================================================

    def _extract_notification_type(
        self,
        text: str,
    ) -> str:

        normalized_text = (
            self.normalize_text(text)
        )

        email_keywords = [
            "email me",
            "send me an email",
            "remind me by email",
            "send reminder by email",
        ]

        for keyword in email_keywords:
            if keyword in normalized_text:
                return "email"

        return "email"

    # =========================================================
    # EMAIL ADDRESS
    # =========================================================

    def _extract_email_address(
        self,
        text: str,
    ) -> Optional[str]:

        email_pattern = (
            r"\b"
            r"[A-Za-z0-9._%+-]+"
            r"@"
            r"[A-Za-z0-9.-]+"
            r"\."
            r"[A-Za-z]{2,}"
            r"\b"
        )

        match = re.search(
            email_pattern,
            text,
        )

        if match:
            return match.group(0)

        return None

    # =========================================================
    # REMINDER MINUTES
    # =========================================================

    def _extract_reminder_minutes_before(
        self,
        text: str,
        deadline: Optional[datetime],
    ) -> Optional[int]:

        normalized_text = (
            self.normalize_text(text)
        )

        now = datetime.now()

        # N minutes before
        match = re.search(
            r"(\d+)\s*minutes?\s*before",
            normalized_text,
        )

        if match:
            return int(match.group(1))

        # N hours before
        match = re.search(
            r"(\d+)\s*hours?\s*before",
            normalized_text,
        )

        if match:
            return int(match.group(1)) * 60

        # Remind me in N minutes
        match = re.search(
            r"remind me in (\d+)\s*minutes?",
            normalized_text,
        )

        if match:
            minutes = int(match.group(1))

            if deadline:
                diff_minutes = max(
                    int(
                        (
                            deadline - now
                        ).total_seconds()
                        / 60
                    ),
                    0,
                )

                if diff_minutes > minutes:
                    return max(
                        diff_minutes - minutes,
                        0,
                    )

            return 0

        # Remind me in N hours
        match = re.search(
            r"remind me in (\d+)\s*hours?",
            normalized_text,
        )

        if match:
            hours = int(match.group(1))

            if deadline:
                diff_minutes = max(
                    int(
                        (
                            deadline - now
                        ).total_seconds()
                        / 60
                    ),
                    0,
                )

                target = hours * 60

                if diff_minutes > target:
                    return max(
                        diff_minutes - target,
                        0,
                    )

            return 0

        # General in N minutes
        match = re.search(
            r"\bin (\d+)\s*minutes?\b",
            normalized_text,
        )

        if match:
            total_minutes = int(
                match.group(1)
            )

            if total_minutes <= 5:
                return 1

            return min(
                5,
                total_minutes - 1,
            )

        # General in N hours
        match = re.search(
            r"\bin (\d+)\s*hours?\b",
            normalized_text,
        )

        if match:
            total_hours = int(
                match.group(1)
            )

            total_minutes = (
                total_hours * 60
            )

            return min(
                60,
                max(
                    total_minutes - 5,
                    5,
                ),
            )

        # Default:
        # reminder 5 minutes before.
        return 5

    # =========================================================
    # RECURRING PATTERN
    # =========================================================

    def _extract_recurring_pattern(
        self,
        text: str,
    ) -> Optional[str]:

        normalized_text = (
            self.normalize_text(text)
        )

        # 5 times per day / 3 times a day
        if re.search(
            r"\b\d+\s+times?\s+"
            r"(?:per\s+day|a\s+day|each\s+day|daily)\b",
            normalized_text,
            re.IGNORECASE,
        ):
            return "daily"

        for pattern, keywords in (
            self.recurring_patterns.items()
        ):
            for keyword in keywords:
                if keyword in normalized_text:
                    return pattern

        return None