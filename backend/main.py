import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from models import (
    Task,
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    ChatMessage,
    ChatResponse,
    User,
    UserLoginRequest,
    UserResponse,
    MeetingRequest,
)

from db import get_db, create_tables, SessionLocal
from parser import TaskParser
from planner import TaskPlanner
from calendar_integration import GoogleCalendarIntegration
from notifications import notification_manager, websocket_endpoint
from recurring_tasks import recurring_task_manager
from meeting_scheduler import meeting_scheduler


task_parser = TaskParser()
task_planner = TaskPlanner()
calendar_integration = GoogleCalendarIntegration()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()

    await notification_manager.start_background_tasks(
        lambda: SessionLocal()
    )

    await recurring_task_manager.start_background_tasks(
        lambda: SessionLocal()
    )

    # Process recurring tasks once on startup
    db = SessionLocal()

    try:
        recurring_task_manager.process_recurring_tasks(db)
    finally:
        db.close()

    yield

    # Shutdown
    notification_manager.stop()
    recurring_task_manager.stop()

app = FastAPI(
    title="Personal Task Management Assistant",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# LOGIN
# ============================================================

@app.post(
    "/login",
    response_model=UserResponse,
)
async def login(
    user_request: UserLoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == user_request.email)
        .first()
    )

    if user:
        return user

    new_user = User(
        email=user_request.email
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


def get_or_create_user(
    db: Session,
    email: str,
) -> User:
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        user = User(
            email=email
        )

        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def get_user_or_404(
    db: Session,
    email: str,
) -> User:
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return user


# ============================================================
# TASK CONFLICT HELPER
# ============================================================

def find_task_time_conflict(
    db: Session,
    user_id: int,
    deadline: Optional[datetime],
    exclude_task_id: Optional[int] = None,
) -> Optional[Task]:
    """Return an existing active task at the exact same deadline, if any."""
    if deadline is None:
        return None

    query = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.deadline == deadline,
            Task.status != "completed",
        )
    )

    if exclude_task_id is not None:
        query = query.filter(Task.id != exclude_task_id)

    return query.first()


# ============================================================
# TASKS
# ============================================================

@app.post(
    "/tasks",
    response_model=TaskResponse,
)
async def create_task(
    task: TaskCreate,
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if not user_email:
        raise HTTPException(
            status_code=400,
            detail="user_email is required",
        )

    user = get_or_create_user(
        db,
        user_email,
    )

    conflicting_task = find_task_time_conflict(
        db,
        user.id,
        task.deadline,
    )

    if conflicting_task:
        conflict_time = conflicting_task.deadline.strftime(
            "%B %d at %I:%M %p"
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Scheduling conflict detected. You already have "
                f"'{conflicting_task.title}' scheduled for {conflict_time}. "
                "Please choose another time."
            ),
        )

    db_task = Task(
        title=task.title,
        description=task.description,
        deadline=task.deadline,
        priority=task.priority,
        estimated_duration=task.estimated_duration,
        category=task.category,
        notification_type=task.notification_type or "email",
        recipient_email=task.recipient_email,
        reminder_minutes_before=task.reminder_minutes_before,
        email_sent=False,
        user_id=user.id,
        is_recurring=task.is_recurring or False,
        recurring_pattern=task.recurring_pattern,
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    await notification_manager.send_task_notification(
        db_task,
        "created",
    )

    return db_task


@app.get(
    "/tasks",
    response_model=List[TaskResponse],
)
async def get_tasks(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = (
            db.query(User)
            .filter(User.email == user_email)
            .first()
        )

        if not user:
            return []

        return (
            db.query(Task)
            .filter(Task.user_id == user.id)
            .all()
        )

    return db.query(Task).all()


@app.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return task


@app.put(
    "/tasks/{task_id}",
    response_model=TaskResponse,
)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    update_data = task_update.dict(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(
            task,
            field,
            value,
        )

    task.updated_at = datetime.now()

    db.commit()
    db.refresh(task)

    if task_update.status == "completed":
        await notification_manager.send_task_notification(
            task,
            "completed",
        )

    else:
        await notification_manager.send_task_notification(
            task,
            "updated",
        )

    return task


@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    await notification_manager.send_task_notification(
        task,
        "deleted",
    )

    db.delete(task)
    db.commit()

    return {
        "message": "Task deleted successfully"
    }


# ============================================================
# CHAT
# ============================================================

@app.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat_with_assistant(
    message: ChatMessage,
    db: Session = Depends(get_db),
):
    if not message.user_email:
        raise HTTPException(
            status_code=400,
            detail="user_email is required",
        )

    user = get_or_create_user(
        db,
        message.user_email,
    )

    parsed_tasks = (
        task_parser.parse_task_from_text(
            message.message
        )
    )

    created_tasks = []
    updated_tasks = []
    conflict_messages = []
    pending_deadlines = {}

    for task_data in parsed_tasks:
        conflicting_task = find_task_time_conflict(
            db,
            user.id,
            task_data.deadline,
        )

        # Also catch two tasks from the same chat request that have the
        # exact same deadline before either one has been committed.
        pending_conflict_title = None
        if task_data.deadline is not None:
            pending_conflict_title = pending_deadlines.get(
                task_data.deadline
            )

        if conflicting_task or pending_conflict_title:
            existing_title = (
                conflicting_task.title
                if conflicting_task
                else pending_conflict_title
            )

            conflict_time = task_data.deadline.strftime(
                "%B %d at %I:%M %p"
            )

            conflict_messages.append(
                f"Scheduling conflict detected. You already have "
                f"'{existing_title}' scheduled for {conflict_time}. "
                "Please choose another time."
            )
            continue

        db_task = Task(
            title=task_data.title,
            description=task_data.description,
            deadline=task_data.deadline,
            priority=task_data.priority,
            estimated_duration=task_data.estimated_duration,
            category=task_data.category,
            notification_type=(
                task_data.notification_type
                or "email"
            ),
            recipient_email=task_data.recipient_email,
            reminder_minutes_before=(
                task_data.reminder_minutes_before
            ),
            email_sent=False,
            user_id=user.id,
            is_recurring=(
                task_data.is_recurring
                or False
            ),
            recurring_pattern=(
                task_data.recurring_pattern
            ),
        )

        db.add(db_task)
        created_tasks.append(db_task)

        if task_data.deadline is not None:
            pending_deadlines[task_data.deadline] = task_data.title

    db.commit()

    for db_task in created_tasks:
        db.refresh(db_task)

    if conflict_messages:
        if created_tasks:
            normal_response = generate_ai_response(
                message.message,
                created_tasks,
                message.user_email,
            )
            response_text = (
                normal_response
                + " "
                + " ".join(conflict_messages)
            )
        else:
            response_text = " ".join(conflict_messages)
    else:
        response_text = generate_ai_response(
            message.message,
            created_tasks,
            message.user_email,
        )

    return ChatResponse(
        response=response_text,
        tasks_created=created_tasks,
        tasks_updated=updated_tasks,
    )


# ============================================================
# CHAT RESPONSE
# ============================================================

def generate_ai_response(
    user_message: str,
    parsed_tasks: List[TaskCreate],
    user_email: Optional[str] = None,
) -> str:

    # --------------------------------------------------------
    # NO TASK CREATED
    # --------------------------------------------------------

    if not parsed_tasks:
        normalized = (
            user_message
            .lower()
            .strip()
        )

        # ----------------------------------------------------
        # SPECIAL CASE:
        # USER EXPLICITLY SAID "TODAY"
        # BUT REQUESTED TIME ALREADY PASSED
        # ----------------------------------------------------

        if "today" in normalized:
            time_match = re.search(
                r"\b(1[0-2]|0?[1-9])"
                r"(?::([0-5]\d))?"
                r"\s*(am|pm)\b",
                normalized,
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
                    time_match
                    .group(3)
                    .lower()
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

                now = datetime.now(
                    ZoneInfo("Europe/Belgrade")
                ).replace(tzinfo=None)

                requested_time = now.replace(
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )

                if requested_time <= now:
                    formatted_time = (
                        requested_time
                        .strftime("%I:%M %p")
                        .lstrip("0")
                    )

                    return (
                        f"{formatted_time} today has already passed. "
                        "Please choose another time."
                    )

        # ----------------------------------------------------
        # NORMAL FALLBACK
        # ----------------------------------------------------

        return (
            "I didn't detect any specific tasks in your message. "
            "Could you try rephrasing it? For example: "
            "'Remind me to send the project tomorrow'"
        )

    # --------------------------------------------------------
    # TASK CREATED
    # --------------------------------------------------------

    task_count = len(parsed_tasks)

    if task_count == 1:
        task = parsed_tasks[0]

        response = (
            f"I've created the task: "
            f"'{task.title}'"
        )

        if task.deadline:
            response += (
                " with deadline "
                + task.deadline.strftime(
                    "%B %d at %I:%M %p"
                )
            )

        if (
            task.priority
            and task.priority > 1
        ):
            priority_text = (
                "high"
                if task.priority == 3
                else "medium"
            )

            response += (
                f" and marked it as "
                f"{priority_text} priority"
            )

        if (
            task.notification_type == "email"
            and user_email
        ):
            response += (
                " and I will send an email reminder "
                f"to {user_email}"
            )

            if task.reminder_minutes_before:
                response += (
                    f" {task.reminder_minutes_before} "
                    "minutes before"
                )

        response += "."

    # --------------------------------------------------------
    # MULTIPLE TASKS
    # --------------------------------------------------------

    else:
        response = (
            f"I've created {task_count} tasks for you: "
        )

        task_titles = [
            f"'{task.title}'"
            for task in parsed_tasks
        ]

        response += (
            ", ".join(task_titles)
            + "."
        )

    response += (
        " Is there anything else you'd like me to help you with?"
    )

    return response


# ============================================================
# SCHEDULE
# ============================================================

@app.get("/schedule")
async def get_schedule(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = get_user_or_404(
            db,
            user_email,
        )

        tasks = (
            db.query(Task)
            .filter(Task.user_id == user.id)
            .all()
        )

    else:
        tasks = db.query(Task).all()

    return task_planner.suggest_schedule(
        tasks
    )


# ============================================================
# CONFLICTS
# ============================================================

@app.get("/conflicts")
async def get_conflicts(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = get_user_or_404(
            db,
            user_email,
        )

        tasks = (
            db.query(Task)
            .filter(Task.user_id == user.id)
            .all()
        )

    else:
        tasks = db.query(Task).all()

    return task_planner.detect_conflicts(
        tasks
    )


# ============================================================
# AUTO RESCHEDULE
# ============================================================

@app.post("/auto-reschedule")
async def auto_reschedule(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = get_user_or_404(
            db,
            user_email,
        )

        tasks = (
            db.query(Task)
            .filter(Task.user_id == user.id)
            .all()
        )

    else:
        tasks = db.query(Task).all()

    conflicts = (
        task_planner.detect_conflicts(
            tasks
        )
    )

    updated_tasks = []

    for conflict in conflicts:
        if conflict["type"] == "overload":
            rescheduled = (
                task_planner.auto_reschedule(
                    tasks,
                    conflict,
                )
            )

            updated_tasks.extend(
                rescheduled
            )

    db.commit()

    return {
        "message": (
            f"Rescheduled "
            f"{len(updated_tasks)} tasks"
        ),
        "updated_tasks": updated_tasks,
    }


# ============================================================
# INSIGHTS
# ============================================================

@app.get("/insights")
async def get_insights(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = get_user_or_404(
            db,
            user_email,
        )

        tasks = (
            db.query(Task)
            .filter(Task.user_id == user.id)
            .all()
        )

    else:
        tasks = db.query(Task).all()

    return (
        task_planner
        .get_productivity_insights(
            tasks
        )
    )


# ============================================================
# GOOGLE CALENDAR STATUS
# ============================================================

@app.get("/calendar/status")
async def get_calendar_status():
    return {
        "authenticated":
            calendar_integration.is_authenticated(),

        "message": (
            "Connected to Google Calendar"
            if calendar_integration.is_authenticated()
            else "Not authenticated"
        ),
    }


# ============================================================
# GOOGLE CALENDAR EVENTS
# ============================================================

@app.get("/calendar/events")
async def get_calendar_events(
    days_ahead: int = 7,
):
    if not calendar_integration.is_authenticated():
        return {
            "error":
                "Not authenticated with Google Calendar"
        }

    events = (
        calendar_integration
        .get_upcoming_events(
            days_ahead
        )
    )

    return {
        "events": events
    }


# ============================================================
# CALENDAR SYNC
# ============================================================

@app.post("/calendar/sync")
async def sync_tasks_to_calendar(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if not calendar_integration.is_authenticated():
        return {
            "error":
                "Not authenticated with Google Calendar"
        }

    if user_email:
        user = get_user_or_404(
            db,
            user_email,
        )

        tasks = (
            db.query(Task)
            .filter(
                Task.user_id == user.id,
                Task.deadline.isnot(None),
                Task.status != "completed",
            )
            .all()
        )

    else:
        tasks = (
            db.query(Task)
            .filter(
                Task.deadline.isnot(None),
                Task.status != "completed",
            )
            .all()
        )

    task_dicts = [
        {
            "id": task.id,
            "title": task.title,
            "description": (
                task.description
                or ""
            ),
            "deadline": (
                task.deadline.isoformat()
                if task.deadline
                else None
            ),
            "estimated_duration": (
                task.estimated_duration
                or 1.0
            ),
        }
        for task in tasks
    ]

    return (
        calendar_integration
        .sync_tasks_to_calendar(
            task_dicts
        )
    )


# ============================================================
# CALENDAR SUMMARY
# ============================================================

@app.get("/calendar/summary")
async def get_calendar_summary(
    days_ahead: int = 7,
):
    if not calendar_integration.is_authenticated():
        return {
            "error":
                "Not authenticated with Google Calendar"
        }

    return (
        calendar_integration
        .get_calendar_summary(
            days_ahead
        )
    )


# ============================================================
# RECURRING TASKS
# ============================================================

@app.post("/recurring/process")
async def process_recurring_tasks(
    db: Session = Depends(get_db),
):
    created_tasks = (
        recurring_task_manager
        .process_recurring_tasks(
            db
        )
    )

    return {
        "message": (
            "Processed recurring tasks, created "
            f"{len(created_tasks)} new instances"
        ),
        "created_tasks": created_tasks,
    }


@app.put(
    "/tasks/{task_id}/complete-recurring"
)
async def complete_recurring_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    success = (
        recurring_task_manager
        .mark_instance_completed(
            db,
            task,
        )
    )

    await notification_manager.send_task_notification(
        task,
        "completed",
    )

    return {
        "message": "Task completed",
        "next_instance_created": success,
    }


# ============================================================
# MEETING SCHEDULER
# ============================================================

def get_user_task_intervals(
    db: Session,
    user_email: Optional[str],
) -> List[tuple]:
    """Return occupied intervals for active tasks belonging to one user."""
    if not user_email:
        return []

    user = (
        db.query(User)
        .filter(User.email == user_email)
        .first()
    )

    if not user:
        return []

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.deadline.isnot(None),
            Task.status != "completed",
        )
        .all()
    )

    intervals = []

    for task in tasks:
        start = task.deadline

        # A task without an estimated duration blocks one hour by default.
        duration_hours = task.estimated_duration or 1.0

        try:
            duration_hours = float(duration_hours)
        except (TypeError, ValueError):
            duration_hours = 1.0

        end = start + timedelta(hours=duration_hours)
        intervals.append((start, end))

    return intervals


@app.post("/meeting/suggest")
async def suggest_meeting_times(
    request: MeetingRequest,
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    task_intervals = get_user_task_intervals(
        db,
        user_email,
    )

    result = (
        meeting_scheduler
        .suggest_meeting_times(
            title=request.title,
            duration_hours=request.duration_hours,
            participants=request.participants,
            preferred_days=request.preferred_days,
            preferred_time_start=request.preferred_time_start,
            preferred_time_end=request.preferred_time_end,
            days_ahead=request.days_ahead,
            task_intervals=task_intervals,
        )
    )

    return result


@app.post("/meeting/best")
async def find_best_meeting_time(
    request: MeetingRequest,
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    task_intervals = get_user_task_intervals(
        db,
        user_email,
    )

    result = (
        meeting_scheduler
        .find_best_meeting_time(
            title=request.title,
            duration_hours=request.duration_hours,
            participants=request.participants,
            urgency=request.urgency,
            task_intervals=task_intervals,
        )
    )

    return result


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket("/ws")
async def websocket_route(
    websocket: WebSocket,
):
    await websocket_endpoint(
        websocket,
        lambda: SessionLocal(),
    )


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
    )