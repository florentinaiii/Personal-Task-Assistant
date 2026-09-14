import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from models import Task
from calendar_integration import GoogleCalendarIntegration

logger = logging.getLogger(__name__)


class MeetingScheduler:
    def __init__(self):
        self.calendar_integration = GoogleCalendarIntegration()
        self.working_hours = {
            "start": 9,  # 9 AM
            "end": 17   # 5 PM
        }
        self.meeting_durations = {
            "short": 0.5,    # 30 minutes
            "standard": 1.0,  # 1 hour
            "long": 2.0      # 2 hours
        }
    
    def suggest_meeting_times(
        self,
        title: str,
        duration_hours: float = 1.0,
        participants: List[str] = None,
        preferred_days: List[int] = None,
        preferred_time_start: int = None,
        preferred_time_end: int = None,
        days_ahead: int = 14
    ) -> Dict:
        """
        Suggest optimal meeting times based on:
        - Calendar availability
        - Participant schedules (if calendar integration available)
        - Preferred time windows
        - Duration requirements
        """
        if participants is None:
            participants = []
        
        if preferred_days is None:
            preferred_days = [0, 1, 2, 3, 4]  # Monday to Friday
        
        suggestions = []
        now = datetime.now()
        
        # Search for available slots
        for days_ahead_count in range(1, days_ahead + 1):
            candidate_date = now + timedelta(days=days_ahead_count)
            
            # Skip if not a preferred day
            if candidate_date.weekday() not in preferred_days:
                continue
            
            # Get available slots for this day
            available_slots = self._find_available_slots(
                candidate_date,
                duration_hours,
                preferred_time_start,
                preferred_time_end
            )
            
            for slot in available_slots:
                # Score this slot
                score = self._score_meeting_slot(
                    slot,
                    candidate_date,
                    preferred_time_start,
                    preferred_time_end
                )
                
                suggestions.append({
                    "date": candidate_date.date().isoformat(),
                    "start_time": slot.isoformat(),
                    "end_time": (slot + timedelta(hours=duration_hours)).isoformat(),
                    "score": score,
                    "duration_hours": duration_hours,
                    "title": title
                })
        
        # Sort by score (highest first)
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top 5 suggestions
        return {
            "title": title,
            "duration_hours": duration_hours,
            "suggestions": suggestions[:5],
            "total_found": len(suggestions)
        }
    
    def _find_available_slots(
        self,
        date: datetime,
        duration_hours: float,
        preferred_start: int = None,
        preferred_end: int = None
    ) -> List[datetime]:
        """Find available time slots on a given date"""
        available_slots = []
        
        # Determine working hours
        work_start = date.replace(
            hour=preferred_start or self.working_hours["start"],
            minute=0,
            second=0,
            microsecond=0
        )
        work_end = date.replace(
            hour=preferred_end or self.working_hours["end"],
            minute=0,
            second=0,
            microsecond=0
        )
        
        # Get existing events from calendar if authenticated
        existing_events = []
        if self.calendar_integration.is_authenticated():
            try:
                events = self.calendar_integration.get_upcoming_events(days_ahead=30)
                # Filter events for this date
                for event in events:
                    if 'dateTime' in event.get('start', {}):
                        event_start = datetime.fromisoformat(
                            event['start']['dateTime'].replace('Z', '+00:00')
                        )
                        if event_start.date() == date.date():
                            existing_events.append(event_start)
            except Exception as e:
                logger.warning(f"Failed to fetch calendar events: {e}")
        
        # Also check for existing tasks with deadlines
        # This would require database access, so we'll skip for now
        
        # Find gaps between events
        current_time = work_start
        
        # Sort existing events by start time
        existing_events.sort()
        
        for event_start in existing_events:
            # Check if there's a gap before this event
            if current_time + timedelta(hours=duration_hours) <= event_start:
                available_slots.append(current_time)
            
            # Move current time to after this event (assume 1 hour duration for calendar events)
            current_time = event_start + timedelta(hours=1)
        
        # Check if there's space after the last event
        if current_time + timedelta(hours=duration_hours) <= work_end:
            available_slots.append(current_time)
        
        # If no events, suggest slots at regular intervals
        if not existing_events:
            slot = work_start
            while slot + timedelta(hours=duration_hours) <= work_end:
                available_slots.append(slot)
                slot += timedelta(hours=1)
        
        return available_slots
    
    def _score_meeting_slot(
        self,
        slot: datetime,
        date: datetime,
        preferred_start: int = None,
        preferred_end: int = None
    ) -> float:
        """Score a meeting slot based on various factors"""
        score = 0.0
        
        # Prefer morning slots (9-11 AM)
        if 9 <= slot.hour < 11:
            score += 30
        # Prefer afternoon slots (2-4 PM)
        elif 14 <= slot.hour < 16:
            score += 20
        # Avoid lunch time (12-1 PM)
        elif 12 <= slot.hour < 13:
            score -= 20
        # Avoid late afternoon (after 4 PM)
        elif slot.hour >= 16:
            score -= 10
        
        # Prefer slots on preferred time
        if preferred_start and preferred_end:
            if preferred_start <= slot.hour < preferred_end:
                score += 40
        
        # Prefer slots earlier in the week
        day_of_week = date.weekday()
        if day_of_week <= 2:  # Monday to Wednesday
            score += 15
        elif day_of_week == 3:  # Thursday
            score += 10
        # Friday is less preferred
        elif day_of_week == 4:
            score += 5
        
        # Prefer slots on the hour or half-hour
        if slot.minute == 0 or slot.minute == 30:
            score += 10
        
        return score
    
    def find_best_meeting_time(
        self,
        title: str,
        duration_hours: float = 1.0,
        participants: List[str] = None,
        urgency: str = "normal"
    ) -> Dict:
        """
        Find the single best meeting time with reasoning
        """
        if urgency == "urgent":
            days_ahead = 3
            preferred_days = [0, 1, 2, 3, 4, 5]  # Include Saturday
        elif urgency == "flexible":
            days_ahead = 21
            preferred_days = [0, 1, 2, 3, 4]
        else:  # normal
            days_ahead = 14
            preferred_days = [0, 1, 2, 3, 4]
        
        result = self.suggest_meeting_times(
            title=title,
            duration_hours=duration_hours,
            participants=participants,
            preferred_days=preferred_days,
            days_ahead=days_ahead
        )
        
        if result["suggestions"]:
            best = result["suggestions"][0]
            return {
                "recommended": True,
                "title": title,
                "date": best["date"],
                "start_time": best["start_time"],
                "end_time": best["end_time"],
                "duration_hours": best["duration_hours"],
                "score": best["score"],
                "reasoning": self._generate_reasoning(best, urgency),
                "alternatives": result["suggestions"][1:3] if len(result["suggestions"]) > 1 else []
            }
        else:
            return {
                "recommended": False,
                "title": title,
                "reasoning": "No suitable time slots found within the specified timeframe. Consider increasing the search window or adjusting duration requirements.",
                "alternatives": []
            }
    
    def _generate_reasoning(self, suggestion: Dict, urgency: str) -> str:
        """Generate human-readable reasoning for the recommendation"""
        slot_time = datetime.fromisoformat(suggestion["start_time"])
        hour = slot_time.hour
        minute = slot_time.minute
        
        time_str = f"{hour}:{minute:02d}"
        
        reasons = []
        
        if 9 <= hour < 11:
            reasons.append("morning slot (optimal for focus)")
        elif 14 <= hour < 16:
            reasons.append("afternoon slot (good for collaboration)")
        
        if slot_time.minute == 0 or slot_time.minute == 30:
            reasons.append("starts on the hour/half-hour")
        
        if urgency == "urgent":
            reasons.append("earliest available slot given urgency")
        
        if not reasons:
            reasons.append("best available time slot")
        
        return f"Recommended because: {', '.join(reasons)}. Score: {suggestion['score']}"


meeting_scheduler = MeetingScheduler()
