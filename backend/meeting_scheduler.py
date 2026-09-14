import logging
from datetime import datetime, timedelta
from typing import List, Dict

from calendar_integration import GoogleCalendarIntegration


logger = logging.getLogger(__name__)


class MeetingScheduler:
    def __init__(self):
        self.calendar_integration = GoogleCalendarIntegration()

        self.working_hours = {
            "start": 9,   # 9 AM
            "end": 17,    # 5 PM
        }

        self.meeting_durations = {
            "short": 0.5,       # 30 minutes
            "standard": 1.0,    # 1 hour
            "medium": 1.5,      # 1.5 hours
            "long": 2.0,        # 2 hours
        }

    # =========================================================
    # SUGGEST MEETING TIMES
    # =========================================================

    def suggest_meeting_times(
        self,
        title: str,
        duration_hours: float = 1.0,
        participants: List[str] = None,
        preferred_days: List[int] = None,
        preferred_time_start: int = None,
        preferred_time_end: int = None,
        days_ahead: int = 14,
    ) -> Dict:
        """
        Suggest optimal meeting times based on:
        - Calendar availability
        - Preferred days
        - Preferred time windows
        - Duration requirements
        """

        if participants is None:
            participants = []

        if preferred_days is None:
            preferred_days = [0, 1, 2, 3, 4]

        # Always normalize duration to float
        try:
            duration_hours = float(duration_hours)
        except (TypeError, ValueError):
            duration_hours = 1.0

        # Supported durations
        allowed_durations = [0.5, 1.0, 1.5, 2.0]

        if duration_hours not in allowed_durations:
            return {
                "title": title,
                "duration_hours": duration_hours,
                "suggestions": [],
                "total_found": 0,
                "error": (
                    "Unsupported meeting duration. "
                    "Please choose 0.5, 1.0, 1.5 or 2.0 hours."
                ),
            }

        suggestions = []
        now = datetime.now()

        for days_ahead_count in range(1, days_ahead + 1):
            candidate_date = now + timedelta(days=days_ahead_count)

            # Skip days outside preferred days
            if candidate_date.weekday() not in preferred_days:
                continue

            available_slots = self._find_available_slots(
                date=candidate_date,
                duration_hours=duration_hours,
                preferred_start=preferred_time_start,
                preferred_end=preferred_time_end,
            )

            for slot in available_slots:
                score = self._score_meeting_slot(
                    slot=slot,
                    date=candidate_date,
                    preferred_start=preferred_time_start,
                    preferred_end=preferred_time_end,
                )

                suggestions.append(
                    {
                        "date": candidate_date.date().isoformat(),
                        "start_time": slot.isoformat(),
                        "end_time": (
                            slot
                            + timedelta(
                                hours=duration_hours
                            )
                        ).isoformat(),
                        "score": score,
                        "duration_hours": duration_hours,
                        "title": title,
                    }
                )

        suggestions.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        return {
            "title": title,
            "duration_hours": duration_hours,
            "suggestions": suggestions[:5],
            "total_found": len(suggestions),
        }

    # =========================================================
    # AVAILABLE SLOTS
    # =========================================================

    def _find_available_slots(
        self,
        date: datetime,
        duration_hours: float,
        preferred_start: int = None,
        preferred_end: int = None,
    ) -> List[datetime]:
        """
        Find available meeting slots.

        Supports:
        - 0.5 hours
        - 1.0 hours
        - 1.5 hours
        - 2.0 hours

        Candidate slots are checked every 30 minutes.
        """

        available_slots = []

        duration_hours = float(duration_hours)

        meeting_duration = timedelta(
            hours=duration_hours
        )

        # -----------------------------------------------------
        # WORKING HOURS
        # -----------------------------------------------------

        start_hour = (
            preferred_start
            if preferred_start is not None
            else self.working_hours["start"]
        )

        end_hour = (
            preferred_end
            if preferred_end is not None
            else self.working_hours["end"]
        )

        work_start = date.replace(
            hour=start_hour,
            minute=0,
            second=0,
            microsecond=0,
        )

        work_end = date.replace(
            hour=end_hour,
            minute=0,
            second=0,
            microsecond=0,
        )

        # Meeting cannot fit at all
        if work_start + meeting_duration > work_end:
            return []

        # -----------------------------------------------------
        # EXISTING CALENDAR EVENTS
        # -----------------------------------------------------

        existing_events = []

        if self.calendar_integration.is_authenticated():
            try:
                events = (
                    self.calendar_integration
                    .get_upcoming_events(
                        days_ahead=30
                    )
                )

                for event in events:
                    start_data = event.get(
                        "start",
                        {},
                    )

                    end_data = event.get(
                        "end",
                        {},
                    )

                    if "dateTime" not in start_data:
                        continue

                    event_start = (
                        datetime.fromisoformat(
                            start_data[
                                "dateTime"
                            ].replace(
                                "Z",
                                "+00:00",
                            )
                        )
                    )

                    if "dateTime" in end_data:
                        event_end = (
                            datetime.fromisoformat(
                                end_data[
                                    "dateTime"
                                ].replace(
                                    "Z",
                                    "+00:00",
                                )
                            )
                        )
                    else:
                        event_end = (
                            event_start
                            + timedelta(hours=1)
                        )

                    # Scheduler uses naive datetimes
                    if event_start.tzinfo is not None:
                        event_start = (
                            event_start.replace(
                                tzinfo=None
                            )
                        )

                    if event_end.tzinfo is not None:
                        event_end = (
                            event_end.replace(
                                tzinfo=None
                            )
                        )

                    if (
                        event_start.date()
                        == date.date()
                    ):
                        existing_events.append(
                            (
                                event_start,
                                event_end,
                            )
                        )

            except Exception as e:
                logger.warning(
                    "Failed to fetch calendar "
                    f"events: {e}"
                )

        existing_events.sort(
            key=lambda event: event[0]
        )

        # -----------------------------------------------------
        # GENERATE SLOTS EVERY 30 MINUTES
        # -----------------------------------------------------

        slot_interval = timedelta(
            minutes=30
        )

        slot = work_start

        while (
            slot + meeting_duration
            <= work_end
        ):
            slot_end = (
                slot + meeting_duration
            )

            conflict = False

            for (
                event_start,
                event_end,
            ) in existing_events:

                # Standard overlap rule
                if (
                    slot < event_end
                    and slot_end > event_start
                ):
                    conflict = True
                    break

            if not conflict:
                available_slots.append(
                    slot
                )

            slot += slot_interval

        return available_slots

    # =========================================================
    # SCORE SLOT
    # =========================================================

    def _score_meeting_slot(
        self,
        slot: datetime,
        date: datetime,
        preferred_start: int = None,
        preferred_end: int = None,
    ) -> float:
        """
        Score a meeting slot.
        """

        score = 0.0

        # Morning 09:00–11:00
        if 9 <= slot.hour < 11:
            score += 30

        # Afternoon 14:00–16:00
        elif 14 <= slot.hour < 16:
            score += 20

        # Lunch
        elif 12 <= slot.hour < 13:
            score -= 20

        # Late afternoon
        elif slot.hour >= 16:
            score -= 10

        # Preferred time range
        if (
            preferred_start is not None
            and preferred_end is not None
        ):
            if (
                preferred_start
                <= slot.hour
                < preferred_end
            ):
                score += 40

        # Monday–Wednesday
        day_of_week = date.weekday()

        if day_of_week <= 2:
            score += 15

        # Thursday
        elif day_of_week == 3:
            score += 10

        # Friday
        elif day_of_week == 4:
            score += 5

        # Prefer hour / half-hour
        if slot.minute in [0, 30]:
            score += 10

        return score

    # =========================================================
    # BEST MEETING TIME
    # =========================================================

    def find_best_meeting_time(
        self,
        title: str,
        duration_hours: float = 1.0,
        participants: List[str] = None,
        urgency: str = "normal",
    ) -> Dict:
        """
        Find the single best meeting time.
        """

        try:
            duration_hours = float(
                duration_hours
            )
        except (TypeError, ValueError):
            duration_hours = 1.0

        # -----------------------------------------------------
        # URGENCY WINDOW
        # -----------------------------------------------------

        if urgency == "urgent":
            days_ahead = 3

            preferred_days = [
                0,
                1,
                2,
                3,
                4,
                5,
            ]

        elif urgency == "flexible":
            days_ahead = 21

            preferred_days = [
                0,
                1,
                2,
                3,
                4,
            ]

        else:
            days_ahead = 14

            preferred_days = [
                0,
                1,
                2,
                3,
                4,
            ]

        result = self.suggest_meeting_times(
            title=title,
            duration_hours=duration_hours,
            participants=participants,
            preferred_days=preferred_days,
            days_ahead=days_ahead,
        )

        # -----------------------------------------------------
        # RESULT
        # -----------------------------------------------------

        if result.get("error"):
            return {
                "recommended": False,
                "title": title,
                "reasoning": result[
                    "error"
                ],
                "alternatives": [],
            }

        if result["suggestions"]:
            best = (
                result["suggestions"][0]
            )

            return {
                "recommended": True,
                "title": title,
                "date": best["date"],
                "start_time": (
                    best["start_time"]
                ),
                "end_time": (
                    best["end_time"]
                ),
                "duration_hours": (
                    best["duration_hours"]
                ),
                "score": best["score"],
                "reasoning": (
                    self._generate_reasoning(
                        best,
                        urgency,
                    )
                ),
                "alternatives": (
                    result[
                        "suggestions"
                    ][1:3]
                    if len(
                        result[
                            "suggestions"
                        ]
                    )
                    > 1
                    else []
                ),
            }

        return {
            "recommended": False,
            "title": title,
            "reasoning": (
                "No suitable time slots found "
                "within the specified timeframe. "
                "Consider increasing the search "
                "window or adjusting duration "
                "requirements."
            ),
            "alternatives": [],
        }

    # =========================================================
    # REASONING
    # =========================================================

    def _generate_reasoning(
        self,
        suggestion: Dict,
        urgency: str,
    ) -> str:
        """
        Generate human-readable reasoning.
        """

        slot_time = datetime.fromisoformat(
            suggestion["start_time"]
        )

        hour = slot_time.hour
        minute = slot_time.minute

        reasons = []

        if 9 <= hour < 11:
            reasons.append(
                "morning slot "
                "(optimal for focus)"
            )

        elif 14 <= hour < 16:
            reasons.append(
                "afternoon slot "
                "(good for collaboration)"
            )

        if minute in [0, 30]:
            reasons.append(
                "starts on the "
                "hour/half-hour"
            )

        if urgency == "urgent":
            reasons.append(
                "earliest available slot "
                "given urgency"
            )

        if not reasons:
            reasons.append(
                "best available time slot"
            )

        duration = suggestion.get(
            "duration_hours",
            1.0,
        )

        if duration == 0.5:
            duration_text = "30 minutes"

        elif duration == 1.0:
            duration_text = "1 hour"

        elif duration == 1.5:
            duration_text = "1.5 hours"

        elif duration == 2.0:
            duration_text = "2 hours"

        else:
            duration_text = (
                f"{duration} hours"
            )

        return (
            "Recommended because: "
            f"{', '.join(reasons)}. "
            f"Duration: {duration_text}. "
            f"Score: {suggestion['score']}"
        )


meeting_scheduler = MeetingScheduler()