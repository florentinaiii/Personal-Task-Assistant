
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
            "daily": ["every day this week", "every day", "daily", "each day"],
            "weekly": ["every week", "weekly", "each week"],
            "monthly": ["every month", "monthly", "each month"],
            "biweekly": ["every two weeks", "biweekly", "every other week"]
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

    def normalize_text(self, text: str) -> str:
        normalized = text.lower().strip()

        for wrong, correct in self.common_misspellings.items():
            normalized = re.sub(rf"\b{re.escape(wrong)}\b", correct, normalized)

        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def parse_task_from_text(self, text: str) -> List[TaskCreate]:
        normalized_text = self.normalize_text(text)

        # Special case: "every day this week".
        # Create one finite task for each remaining day of the week instead of
        # creating an endless daily recurring task.
        if "every day this week" in normalized_text:
            tasks = self._create_tasks_for_this_week(normalized_text, text)
            if tasks:
                return tasks

        # Check for "in X minutes" pattern first - this has highest priority
        in_minutes_match = re.search(r"\bin\s+(\d+)\s*minutes?\b", normalized_text, re.IGNORECASE)
        if in_minutes_match:
            # This is an immediate reminder task
            task = self._extract_single_task(normalized_text, text)
            if task:
                # Override deadline with now + X minutes
                task.deadline = datetime.now() + timedelta(minutes=int(in_minutes_match.group(1)))
                # Set reminder to trigger 1 minute before (or immediately if very short)
                if int(in_minutes_match.group(1)) <= 2:
                    task.reminder_minutes_before = 1
                elif int(in_minutes_match.group(1)) <= 5:
                    task.reminder_minutes_before = int(in_minutes_match.group(1)) - 1
                else:
                    task.reminder_minutes_before = min(5, int(in_minutes_match.group(1)) - 1)
                # Force email notification
                task.notification_type = "email"
            return [task] if task else []

        if any(
            phrase in normalized_text
            for phrase in [
                "remind me",
                "before",
                "after",
                "at",
                "email me",
                "send me an email",
                "today",
                "tomorrow",
            ]
        ):
            task = self._extract_single_task(normalized_text, text)
            return [task] if task else []

        task_segments = re.split(r";|\band\b|\balso\b|\bplus\b", normalized_text, flags=re.IGNORECASE)

        tasks = []
        for segment in task_segments:
            segment = segment.strip()
            if len(segment) < 3:
                continue

            task = self._extract_single_task(segment, text)
            if task:
                tasks.append(task)

        return tasks

    def _create_tasks_for_this_week(
        self,
        normalized_text: str,
        original_text: str,
    ) -> List[TaskCreate]:
        """
        Handle "every day this week" as a finite recurrence.

        One independent task is created for each remaining day through Sunday.
        If the current week has no valid future occurrence left (for example,
        Sunday after the requested time), the next Monday-Sunday week is used.
        """
        template = self._extract_single_task(normalized_text, original_text)
        if not template:
            return []

        now = datetime.now()

        # Determine the requested time.
        time_match = re.search(
            r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm)\b",
            normalized_text,
            re.IGNORECASE,
        )

        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridiem = time_match.group(3).lower()

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

        # Sunday is weekday 6 in Python.
        days_until_sunday = 6 - now.weekday()
        week_end = (now + timedelta(days=days_until_sunday)).date()

        first_candidate = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        if first_candidate <= now:
            first_candidate += timedelta(days=1)

        # If no valid time remains in the current week, use next week.
        if first_candidate.date() > week_end:
            days_until_next_monday = 7 - now.weekday()
            next_monday = (now + timedelta(days=days_until_next_monday)).date()
            first_candidate = datetime.combine(
                next_monday,
                datetime.min.time(),
            ).replace(hour=hour, minute=minute)
            week_end = next_monday + timedelta(days=6)

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
                    # These instances are intentionally finite, so they are
                    # stored as normal tasks and do not continue after Sunday.
                    is_recurring=False,
                    recurring_pattern=None,
                )
            )
            current += timedelta(days=1)

        return tasks

    def _extract_single_task(self, text: str, original_text: Optional[str] = None) -> Optional[TaskCreate]:
        if original_text is None:
            original_text = text

        cleaned = re.sub(
            r"\b(remind me to|remember to|don't forget to|need to|have to|should)\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        if not cleaned:
            return None

        # Check if this is an "in X minutes" task
        in_minutes_match = re.search(r"\bin\s+(\d+)\s*minutes?\b", self.normalize_text(original_text), re.IGNORECASE)
        if in_minutes_match:
            # For "in X minutes" tasks, extract the main action part
            main_action = re.sub(r"\bin\s+\d+\s*minutes?\b", "", original_text, flags=re.IGNORECASE).strip()
            cleaned = re.sub(
                r"\b(remind me to|remember to|don't forget to|need to|have to|should)\b",
                "",
                main_action,
                flags=re.IGNORECASE,
            ).strip()
            
            deadline = datetime.now() + timedelta(minutes=int(in_minutes_match.group(1)))
            priority = self._extract_priority(cleaned)
            duration = self._extract_duration(cleaned)
            title = self._clean_title(cleaned)
            
            # Set reminder timing
            minutes = int(in_minutes_match.group(1))
            if minutes <= 2:
                reminder_minutes_before = 1
            elif minutes <= 5:
                reminder_minutes_before = minutes - 1
            else:
                reminder_minutes_before = min(5, minutes - 1)
            
            notification_type = "email"
            recipient_email = self._extract_email_address(original_text)
            recurring_pattern = self._extract_recurring_pattern(original_text)
            is_recurring = recurring_pattern is not None
            
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
        
        # Regular task extraction (not "in X minutes")
        recurring_pattern = self._extract_recurring_pattern(text)
        is_recurring = recurring_pattern is not None

        deadline = self._extract_deadline(cleaned)

        # Recurring tasks must always start with a future deadline.
        if is_recurring and (deadline is None or deadline <= datetime.now()):
            deadline = self._calculate_initial_recurring_deadline(
                text=text,
                pattern=recurring_pattern,
                parsed_deadline=deadline,
            )

        priority = self._extract_priority(cleaned)
        duration = self._extract_duration(cleaned)
        title = self._clean_title(cleaned)

        notification_type = self._extract_notification_type(text)
        recipient_email = self._extract_email_address(text)
        reminder_minutes_before = self._extract_reminder_minutes_before(text, deadline)

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

    def _extract_deadline(self, text: str) -> Optional[datetime]:
        now = datetime.now()

        def extract_explicit_time(value: str):
            """Parse 5pm, 5 pm, 5:00pm, 5:30 pm, etc."""
            match = re.search(
                r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm)\b",
                value,
                re.IGNORECASE,
            )
            if not match:
                return None

            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            meridiem = match.group(3).lower()

            if meridiem == "pm" and hour != 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0

            return hour, minute

        explicit_time = extract_explicit_time(text)

        match = re.search(r"\bin (\d+)\s*minutes?\b", text, re.IGNORECASE)
        if match:
            return now + timedelta(minutes=int(match.group(1)))

        match = re.search(r"\bin (\d+)\s*hours?\b", text, re.IGNORECASE)
        if match:
            return now + timedelta(hours=int(match.group(1)))

        match = re.search(r"\bin (\d+)\s*days?\b", text, re.IGNORECASE)
        if match:
            base_date = now + timedelta(days=int(match.group(1)))
            if explicit_time:
                hour, minute = explicit_time
                return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return base_date.replace(hour=23, minute=59, second=0, microsecond=0)

        if "tomorrow" in text.lower():
            base_date = now + timedelta(days=1)
            if explicit_time:
                hour, minute = explicit_time
                return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return base_date.replace(hour=23, minute=59, second=0, microsecond=0)

        if "today" in text.lower():
            if explicit_time:
                hour, minute = explicit_time
                return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return now.replace(hour=23, minute=59, second=0, microsecond=0)

        if explicit_time and any(word in text.lower() for word in ["at", "by", "before"]):
            hour, minute = explicit_time
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate < now:
                candidate += timedelta(days=1)
            return candidate

        patterns = [
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}-\d{1,2}-\d{4})",
            r"(next \w+)",
            r"(\w+ \d{1,2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    parsed_date = date_parser.parse(match.group(1), fuzzy=True)
                    if explicit_time:
                        hour, minute = explicit_time
                        parsed_date = parsed_date.replace(
                            hour=hour, minute=minute, second=0, microsecond=0
                        )
                    elif parsed_date.time() == datetime.min.time():
                        parsed_date = parsed_date.replace(hour=23, minute=59)
                    return parsed_date
                except Exception:
                    continue

        return None

    def _calculate_initial_recurring_deadline(
        self,
        text: str,
        pattern: str,
        parsed_deadline: Optional[datetime] = None,
    ) -> datetime:
        """Calculate the first valid future occurrence for a recurring task."""
        now = datetime.now()

        time_match = re.search(
            r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm)\b",
            text,
            re.IGNORECASE,
        )

        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridiem = time_match.group(3).lower()

            if meridiem == "pm" and hour != 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
        elif parsed_deadline:
            hour = parsed_deadline.hour
            minute = parsed_deadline.minute
        else:
            hour = 23
            minute = 59

        if pattern == "daily":
            candidate = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate

        if pattern == "weekly":
            return (now + timedelta(weeks=1)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

        if pattern == "biweekly":
            return (now + timedelta(weeks=2)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

        if pattern == "monthly":
            import calendar

            year = now.year
            month = now.month + 1
            if month == 13:
                year += 1
                month = 1

            max_day = calendar.monthrange(year, month)[1]
            day = min(now.day, max_day)

            return now.replace(
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        return (now + timedelta(days=1)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

    def _extract_priority(self, text: str) -> int:
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

    def _extract_duration(self, text: str) -> Optional[float]:
        patterns = [
            r"(\d+) hours?",
            r"(\d+) hrs?",
            r"(\d+) h\b",
            r"(\d+) minutes?",
            r"(\d+) mins?",
            r"(\d+) min\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = int(match.group(1))
                if any(x in pattern for x in ["hour", "hr", " h"]):
                    return float(value)
                return value / 60.0

        return None

    def _clean_title(self, text: str) -> str:
        """
        Build a clean task title by removing recurrence phrases,
        reminder wording, dates/times, priorities and leftover filler words.
        """
        cleaned = text.strip()

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
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
        
        priority_phrase_patterns = [
            r",?\s*it\s+is\s+(?:very\s+|extremely\s+)?(?:urgent|important|critical|high priority|low priority)\b",
            r",?\s*it's\s+(?:very\s+|extremely\s+)?(?:urgent|important|critical|high priority|low priority)\b",
            r",?\s*this\s+is\s+(?:very\s+|extremely\s+)?(?:urgent|important|critical|high priority|low priority)\b",
        ]

        for pattern in priority_phrase_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        recurring_patterns = [
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
            r"\bthis\s+week\b",
        ]
        for pattern in recurring_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        reminder_patterns = [
            r",?\s*remind me in \d+\s*minutes?",
            r",?\s*remind me before \d{1,2}:\d{2}\s*o'?clock?",
            r",?\s*remind me before \d{1,2}:\d{2}",
            r",?\s*remind me at \d{1,2}(?::\d{2})?\s*(?:am|pm)?",
            r",?\s*email me\b.*$",
            r",?\s*send me an email\b.*$",
            r",?\s*remind me\b.*$",
        ]
        for pattern in reminder_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        time_patterns = [
            r"\b(tomorrow|today|next week|next month)\b",
            r"\bin \d+\s*(?:days?|hours?|minutes?)\b",
            r"\b(?:at|by|before)\s+(?:1[0-2]|0?[1-9])(?::[0-5]\d)?\s*(?:am|pm)\b",
            r"\b(?:1[0-2]|0?[1-9])(?::[0-5]\d)?\s*(?:am|pm)\b",
            r"\bon \w+ \d+\b",
            r"\bon \d+/\d+/\d+\b",
            r"\b\d+/\d+/\d+\b",
            r"\b\d+ hours?\b",
            r"\b\d+ hrs?\b",
            r"\b\d+ minutes?\b",
            r"\b\d+ mins?\b",
        ]
        for pattern in time_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        for word in sorted(self.priority_keywords.keys(), key=len, reverse=True):
            cleaned = re.sub(
                rf"\b{re.escape(word)}\b",
                " ",
                cleaned,
                flags=re.IGNORECASE,
            )

        cleaned = re.sub(r"^\s*i\s+", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*to\s+", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(a|an|the)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")

        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        return cleaned

    def _extract_notification_type(self, text: str) -> str:
        normalized_text = self.normalize_text(text)

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

    def _extract_email_address(self, text: str) -> Optional[str]:
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z|a-z]{2,}\b"
        match = re.search(email_pattern, text)
        if match:
            return match.group(0)
        return None

    def _extract_reminder_minutes_before(self, text: str, deadline: Optional[datetime]) -> Optional[int]:
        normalized_text = self.normalize_text(text)
        now = datetime.now()

        minutes_before_pattern = r"(\d+)\s*minutes?\s*before"
        match = re.search(minutes_before_pattern, normalized_text)
        if match:
            return int(match.group(1))

        hours_before_pattern = r"(\d+)\s*hours?\s*before"
        match = re.search(hours_before_pattern, normalized_text)
        if match:
            return int(match.group(1)) * 60

        match = re.search(r"remind me in (\d+)\s*minutes?", normalized_text)
        if match:
            minutes = int(match.group(1))
            if deadline:
                diff_minutes = max(int((deadline - now).total_seconds() / 60), 0)
                if diff_minutes > minutes:
                    return max(diff_minutes - minutes, 0)
            return 0

        match = re.search(r"remind me in (\d+)\s*hours?", normalized_text)
        if match:
            hours = int(match.group(1))
            if deadline:
                diff_minutes = max(int((deadline - now).total_seconds() / 60), 0)
                target = hours * 60
                if diff_minutes > target:
                    return max(diff_minutes - target, 0)
            return 0

        match = re.search(r"\bin (\d+)\s*minutes?\b", normalized_text)
        if match:
            total_minutes = int(match.group(1))
            if total_minutes <= 5:
                return 1
            return min(5, total_minutes - 1)

        match = re.search(r"\bin (\d+)\s*hours?\b", normalized_text)
        if match:
            total_hours = int(match.group(1))
            total_minutes = total_hours * 60
            return min(60, max(total_minutes - 5, 5))

        return 5

    def _extract_recurring_pattern(self, text: str) -> Optional[str]:
        """Extract recurring pattern from text"""
        normalized_text = self.normalize_text(text)
        
        for pattern, keywords in self.recurring_patterns.items():
            for keyword in keywords:
                if keyword in normalized_text:
                    return pattern
        
        return None