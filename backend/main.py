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
    UserAuthRequest,
    UserResponse,
    AuthResponse,
    MeetingRequest,
)

from db import get_db, create_tables, SessionLocal
from parser import TaskParser
from llm_parser import LLMTaskParser
from planner import TaskPlanner
from calendar_integration import GoogleCalendarIntegration
from notifications import notification_manager, websocket_endpoint
from recurring_tasks import recurring_task_manager
from meeting_scheduler import meeting_scheduler
from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    normalize_email,
    validate_password,
    verify_password,
)


task_parser = TaskParser()
llm_task_parser = LLMTaskParser()
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
# AUTHENTICATION
# ============================================================

@app.post("/register", response_model=AuthResponse)
async def register(
    user_request: UserAuthRequest,
    db: Session = Depends(get_db),
):
    email = normalize_email(user_request.email)
    validate_password(user_request.password)

    user = db.query(User).filter(User.email == email).first()

    if user and user.password_hash:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    if user:
        # Legacy account created before password authentication was introduced.
        user.password_hash = hash_password(user_request.password)
    else:
        user = User(
            email=email,
            password_hash=hash_password(user_request.password),
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    return AuthResponse(
        access_token=create_access_token(user),
        user=user,
    )


@app.post("/login", response_model=AuthResponse)
async def login(
    user_request: UserAuthRequest,
    db: Session = Depends(get_db),
):
    email = normalize_email(user_request.email)
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    if not user.password_hash:
        raise HTTPException(
            status_code=403,
            detail=(
                "This is an existing account from the previous version. "
                "Choose Create account once to set a password."
            ),
        )

    if not verify_password(user_request.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    return AuthResponse(
        access_token=create_access_token(user),
        user=user,
    )


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

def get_owned_task_or_404(
    db: Session,
    task_id: int,
    current_user: User,
) -> Task:
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.user_id == current_user.id,
        )
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@app.post("/tasks", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conflicting_task = find_task_time_conflict(
        db,
        current_user.id,
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
        user_id=current_user.id,
        is_recurring=task.is_recurring or False,
        recurring_pattern=task.recurring_pattern,
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    await notification_manager.send_task_notification(db_task, "created")
    return db_task


@app.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Task)
        .filter(Task.user_id == current_user.id)
        .all()
    )


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_owned_task_or_404(db, task_id, current_user)


@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = get_owned_task_or_404(db, task_id, current_user)

    update_data = task_update.model_dump(exclude_unset=True)

    if "deadline" in update_data:
        conflict = find_task_time_conflict(
            db,
            current_user.id,
            update_data["deadline"],
            exclude_task_id=task.id,
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail="Scheduling conflict detected. Please choose another time.",
            )

    for field, value in update_data.items():
        setattr(task, field, value)

    task.updated_at = datetime.now()
    db.commit()
    db.refresh(task)

    if task_update.status == "completed":
        await notification_manager.send_task_notification(task, "completed")
    else:
        await notification_manager.send_task_notification(task, "updated")

    return task


@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = get_owned_task_or_404(db, task_id, current_user)

    await notification_manager.send_task_notification(task, "deleted")
    db.delete(task)
    db.commit()

    return {"message": "Task deleted successfully"}


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
    current_user: User = Depends(get_current_user),
):
    user = current_user

    parsed_tasks = (
        llm_task_parser.parse_task_from_text(
            message.message,
            current_user.email,
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
                current_user.email,
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
            current_user.email,
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
        # SPECIAL CASE:
        # USER PROVIDED AN EXPLICIT CALENDAR DATE IN THE PAST
        # ----------------------------------------------------

        date_match = re.search(
            r"\b(0?[1-9]|[12]\d|3[01])[./-]"
            r"(0?[1-9]|1[0-2])[./-]"
            r"(\d{4})\b",
            normalized,
        )

        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year = int(date_match.group(3))

            now = datetime.now(
                ZoneInfo("Europe/Belgrade")
            ).replace(tzinfo=None)

            time_match = re.search(
                r"\b(1[0-2]|0?[1-9])"
                r"(?::([0-5]\d))?"
                r"\s*(am|pm)\b",
                normalized,
                re.IGNORECASE,
            )

            hour = 23
            minute = 59

            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                meridiem = time_match.group(3).lower()

                if meridiem == "pm" and hour != 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0

            try:
                requested_datetime = datetime(
                    year,
                    month,
                    day,
                    hour,
                    minute,
                )
            except ValueError:
                requested_datetime = None

            if (
                requested_datetime is not None
                and requested_datetime <= now
            ):
                formatted_date = requested_datetime.strftime(
                    "%B %d, %Y"
                ).replace(" 0", " ")

                if time_match:
                    formatted_time = requested_datetime.strftime(
                        "%I:%M %p"
                    ).lstrip("0")

                    return (
                        f"{formatted_date} at {formatted_time} "
                        "has already passed. "
                        "Please choose a future date and time."
                    )

                return (
                    f"{formatted_date} has already passed. "
                    "Please choose a future date."
                )

        # ----------------------------------------------------
        # SPECIAL CASE:
        # USER PROVIDED A NAMED CALENDAR DATE IN THE PAST
        # Examples: "March 02 2026", "March 2, 2026"
        # ----------------------------------------------------

        named_date_match = re.search(
            r"\b("
            r"january|february|march|april|may|june|"
            r"july|august|september|october|november|december"
            r")\s+(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
            r",?\s+(\d{4})\b",
            normalized,
            re.IGNORECASE,
        )

        if named_date_match:
            month_names = {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
            }

            month = month_names[named_date_match.group(1).lower()]
            day = int(named_date_match.group(2))
            year = int(named_date_match.group(3))

            now = datetime.now(
                ZoneInfo("Europe/Belgrade")
            ).replace(tzinfo=None)

            time_match = re.search(
                r"\b(1[0-2]|0?[1-9])"
                r"(?::([0-5]\d))?"
                r"\s*(am|pm)\b",
                normalized,
                re.IGNORECASE,
            )

            hour = 23
            minute = 59

            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                meridiem = time_match.group(3).lower()

                if meridiem == "pm" and hour != 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0

            try:
                requested_datetime = datetime(
                    year,
                    month,
                    day,
                    hour,
                    minute,
                )
            except ValueError:
                requested_datetime = None

            if (
                requested_datetime is not None
                and requested_datetime <= now
            ):
                formatted_date = requested_datetime.strftime(
                    "%B %d, %Y"
                ).replace(" 0", " ")

                if time_match:
                    formatted_time = requested_datetime.strftime(
                        "%I:%M %p"
                    ).lstrip("0")

                    return (
                        f"{formatted_date} at {formatted_time} "
                        "has already passed. "
                        "Please choose a future date and time."
                    )

                return (
                    f"{formatted_date} has already passed. "
                    "Please choose a future date."
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

def get_current_user_tasks(db: Session, current_user: User) -> List[Task]:
    return (
        db.query(Task)
        .filter(Task.user_id == current_user.id)
        .all()
    )


@app.get("/schedule")
async def get_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_planner.suggest_schedule(
        get_current_user_tasks(db, current_user)
    )


# ============================================================
# CONFLICTS
# ============================================================

@app.get("/conflicts")
async def get_conflicts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_planner.detect_conflicts(
        get_current_user_tasks(db, current_user)
    )


# ============================================================
# AUTO RESCHEDULE
# ============================================================

@app.post("/auto-reschedule")
async def auto_reschedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tasks = get_current_user_tasks(db, current_user)
    conflicts = task_planner.detect_conflicts(tasks)
    updated_tasks = []

    for conflict in conflicts:
        if conflict["type"] == "overload":
            rescheduled = task_planner.auto_reschedule(tasks, conflict)
            updated_tasks.extend(rescheduled)

    db.commit()

    return {
        "message": f"Rescheduled {len(updated_tasks)} tasks",
        "updated_tasks": updated_tasks,
    }


# ============================================================
# INSIGHTS
# ============================================================

@app.get("/insights")
async def get_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_planner.get_productivity_insights(
        get_current_user_tasks(db, current_user)
    )


# ============================================================
# GOOGLE CALENDAR STATUS
# ============================================================

@app.get("/calendar/status")
async def get_calendar_status(
    current_user: User = Depends(get_current_user),
):
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
    current_user: User = Depends(get_current_user),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not calendar_integration.is_authenticated():
        return {"error": "Not authenticated with Google Calendar"}

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == current_user.id,
            Task.deadline.isnot(None),
            Task.status != "completed",
        )
        .all()
    )

    task_dicts = [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description or "",
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "estimated_duration": task.estimated_duration or 1.0,
        }
        for task in tasks
    ]

    return calendar_integration.sync_tasks_to_calendar(task_dicts)


# ============================================================
# CALENDAR SUMMARY
# ============================================================

@app.get("/calendar/summary")
async def get_calendar_summary(
    days_ahead: int = 7,
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
):
    task = get_owned_task_or_404(
        db,
        task_id,
        current_user,
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
    user_id: int,
) -> List[tuple]:
    """Return occupied intervals for active tasks belonging to one user."""
    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task_intervals = get_user_task_intervals(
        db,
        current_user.id,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task_intervals = get_user_task_intervals(
        db,
        current_user.id,
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