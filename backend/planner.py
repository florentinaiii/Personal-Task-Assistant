from datetime import datetime, timedelta
from typing import List, Dict, Optional
from models import Task, TaskCreate
import heapq

class TaskPlanner:
    def __init__(self):
        self.priority_weights = {1: 1.0, 2: 2.0, 3: 3.0}
        self.urgency_threshold_hours = 24
    
    def prioritize_tasks(self, tasks: List[Task]) -> List[Task]:
        """Prioritize tasks based on deadline, priority, and estimated duration"""
        if not tasks:
            return []
        
        # Calculate priority score for each task
        scored_tasks = []
        for task in tasks:
            if task.status == "completed":
                continue
                
            score = self._calculate_priority_score(task)
            scored_tasks.append((score, task))
        
        # Sort by score (highest first)
        scored_tasks.sort(key=lambda x: x[0], reverse=True)
        
        return [task for score, task in scored_tasks]
    
    def _calculate_priority_score(self, task: Task) -> float:
        """Calculate priority score for a task"""
        score = 0.0
        
        # Base priority weight
        score += self.priority_weights.get(task.priority, 1.0) * 100
        
        # Urgency based on deadline
        if task.deadline:
            now = datetime.now()
            hours_until_deadline = (task.deadline - now).total_seconds() / 3600
            
            if hours_until_deadline < 0:  # Overdue
                score += 1000
            elif hours_until_deadline < self.urgency_threshold_hours:
                # Add urgency score (more urgent = higher score)
                urgency_score = (self.urgency_threshold_hours - hours_until_deadline) * 2
                score += urgency_score
        
        # Consider estimated duration (shorter tasks might get priority boost)
        if task.estimated_duration:
            if task.estimated_duration <= 1:  # Quick tasks
                score += 20
            elif task.estimated_duration <= 2:  # Medium tasks
                score += 10
        
        return score
    
    def suggest_schedule(self, tasks: List[Task], working_hours: int = 8) -> Dict:
        """Suggest an optimal schedule for tasks"""
        prioritized_tasks = self.prioritize_tasks(tasks)
        
        schedule = {
            "today": [],
            "tomorrow": [],
            "this_week": [],
            "overdue": []
        }
        
        now = datetime.now()
        today_end = now.replace(hour=23, minute=59)
        tomorrow_end = today_end + timedelta(days=1)
        week_end = now + timedelta(days=7)
        
        total_daily_capacity = working_hours  # hours per day
        today_used = 0
        
        for task in prioritized_tasks:
            if task.deadline and task.deadline < now:
                schedule["overdue"].append(task)
            elif task.deadline and task.deadline <= today_end:
                if today_used + (task.estimated_duration or 1) <= total_daily_capacity:
                    schedule["today"].append(task)
                    today_used += task.estimated_duration or 1
                else:
                    schedule["tomorrow"].append(task)
            elif task.deadline and task.deadline <= tomorrow_end:
                schedule["tomorrow"].append(task)
            elif task.deadline and task.deadline <= week_end:
                schedule["this_week"].append(task)
            else:
                # No deadline or far deadline, add to today if capacity allows
                if today_used + (task.estimated_duration or 1) <= total_daily_capacity:
                    schedule["today"].append(task)
                    today_used += task.estimated_duration or 1
                else:
                    schedule["this_week"].append(task)
        
        return schedule
    
    def detect_conflicts(self, tasks: List[Task]) -> List[Dict]:
        """Detect potential scheduling conflicts"""
        conflicts = []
        
        # Group tasks by deadline
        deadline_groups = {}
        for task in tasks:
            if task.deadline and task.status != "completed":
                deadline_key = task.deadline.date()
                if deadline_key not in deadline_groups:
                    deadline_groups[deadline_key] = []
                deadline_groups[deadline_key].append(task)
        
        # Check for conflicts in each day
        for date, day_tasks in deadline_groups.items():
            total_duration = sum(task.estimated_duration or 1 for task in day_tasks)
            
            if total_duration > 8:  # More than 8 hours in a day
                conflicts.append({
                    "type": "overload",
                    "date": date,
                    "total_hours": total_duration,
                    "tasks": day_tasks
                })
        
        # Check for overdue tasks
        now = datetime.now()
        overdue_tasks = [task for task in tasks if task.deadline and task.deadline < now and task.status != "completed"]
        if overdue_tasks:
            conflicts.append({
                "type": "overdue",
                "tasks": overdue_tasks
            })
        
        return conflicts
    
    def find_next_available_day(self, task: Task, all_tasks: List[Task], start_date: datetime, max_days_ahead: int = 14) -> Optional[datetime]:
        """Find the next available day with enough capacity for the task"""
        task_duration = task.estimated_duration or 1.0
        
        for days_ahead in range(1, max_days_ahead + 1):
            candidate_date = (start_date + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
            candidate_date_end = candidate_date.replace(hour=23, minute=59)
            
            # Check if this day would violate the task's deadline
            if task.deadline and candidate_date > task.deadline:
                continue  # Can't schedule after the deadline
            
            # Calculate total scheduled duration for this day
            day_tasks = [t for t in all_tasks 
                        if t.deadline and t.deadline.date() == candidate_date.date() 
                        and t.id != task.id and t.status != "completed"]
            
            total_duration = sum(t.estimated_duration or 1.0 for t in day_tasks)
            
            # Check if there's enough capacity (8-hour workday)
            if total_duration + task_duration <= 8.0:
                # Find a specific time slot within the day
                available_time = self._find_time_slot(candidate_date, day_tasks, task_duration)
                if available_time:
                    return available_time
        
        return None
    
    def _find_time_slot(self, date_start: datetime, existing_tasks: List[Task], duration: float) -> Optional[datetime]:
        """Find a specific time slot within a day for the task"""
        # Sort existing tasks by start time
        existing_tasks.sort(key=lambda t: t.deadline)
        
        # Start from beginning of workday (9 AM)
        work_start = date_start.replace(hour=9, minute=0)
        work_end = date_start.replace(hour=17, minute=0)
        
        current_time = work_start
        
        for task in existing_tasks:
            if task.deadline:
                task_start = task.deadline - timedelta(hours=task.estimated_duration or 1.0)
                # Check if there's a gap before this task
                if current_time + timedelta(hours=duration) <= task_start:
                    return current_time
                # Move to after this task
                current_time = task.deadline
        
        # Check if there's space after the last task
        if current_time + timedelta(hours=duration) <= work_end:
            return current_time
        
        return None
    
    def auto_reschedule(self, tasks: List[Task], conflict: Dict) -> List[Task]:
        """Automatically reschedule tasks to resolve conflicts"""
        updated_tasks = []
        
        if conflict["type"] == "overload":
            conflict_tasks = conflict["tasks"]
            conflict_date = conflict["date"]
            
            # Sort conflicting tasks by priority score (highest first)
            conflict_tasks.sort(key=lambda t: self._calculate_priority_score(t), reverse=True)
            
            # Calculate total duration and excess
            total_duration = sum(task.estimated_duration or 1 for task in conflict_tasks)
            excess = total_duration - 8
            
            # Keep high-priority tasks, try to move lower-priority ones
            tasks_to_move = []
            moved_duration = 0
            
            # Start from lowest priority tasks
            for task in reversed(conflict_tasks):
                if moved_duration >= excess:
                    break
                
                task_duration = task.estimated_duration or 1
                
                # Find next available day for this task
                next_available = self.find_next_available_day(task, tasks, conflict_date)
                
                if next_available:
                    # Check if moving would violate deadline constraint
                    if not task.deadline or next_available <= task.deadline:
                        # Update the task deadline
                        old_deadline = task.deadline
                        task.deadline = next_available
                        updated_tasks.append(task)
                        moved_duration += task_duration
                    else:
                        # Can't move without violating deadline
                        tasks_to_move.append(task)
                else:
                    # No available day found
                    tasks_to_move.append(task)
            
            # If we still have excess, try moving medium priority tasks
            if moved_duration < excess and tasks_to_move:
                for task in tasks_to_move:
                    if moved_duration >= excess:
                        break
                    
                    task_duration = task.estimated_duration or 1
                    
                    # Try to find a slot even with partial capacity
                    next_available = self.find_next_available_day(task, tasks, conflict_date, max_days_ahead=21)
                    
                    if next_available and (not task.deadline or next_available <= task.deadline):
                        old_deadline = task.deadline
                        task.deadline = next_available
                        updated_tasks.append(task)
                        moved_duration += task_duration
        
        return updated_tasks
    
    def get_productivity_insights(self, tasks: List[Task]) -> Dict:
        """Generate productivity insights from task data"""
        insights = {
            "completion_rate": 0,
            "avg_task_duration": 0,
            "priority_distribution": {1: 0, 2: 0, 3: 0},
            "overdue_count": 0,
            "upcoming_deadlines": []
        }
        
        if not tasks:
            return insights
        
        completed_tasks = [t for t in tasks if t.status == "completed"]
        total_tasks = len(tasks)
        
        if total_tasks > 0:
            insights["completion_rate"] = len(completed_tasks) / total_tasks
        
        # Calculate average duration
        tasks_with_duration = [t for t in tasks if t.estimated_duration]
        if tasks_with_duration:
            insights["avg_task_duration"] = sum(t.estimated_duration for t in tasks_with_duration) / len(tasks_with_duration)
        
        # Priority distribution
        for task in tasks:
            insights["priority_distribution"][task.priority] += 1
        
        # Count overdue
        now = datetime.now()
        insights["overdue_count"] = len([t for t in tasks if t.deadline and t.deadline < now and t.status != "completed"])
        
        # Upcoming deadlines (next 3 days)
        upcoming_deadline_tasks = [t for t in tasks if t.deadline and now < t.deadline <= now + timedelta(days=3) and t.status != "completed"]
        upcoming_deadline_tasks.sort(key=lambda t: t.deadline)
        insights["upcoming_deadlines"] = upcoming_deadline_tasks[:5]  # Top 5
        
        return insights
