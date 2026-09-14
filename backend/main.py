from datetime import datetime
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
    await notification_manager.start_background_tasks(lambda: SessionLocal())
    # Process recurring tasks on startup
    db = SessionLocal()
    try:
        recurring_task_manager.process_recurring_tasks(db)
    finally:
        db.close()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="Personal Task Management Assistant",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/login", response_model=UserResponse)
async def login(user_request: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_request.email).first()

    if user:
        return user

    new_user = User(email=user_request.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def get_or_create_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_user_or_404(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/tasks", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if not user_email:
        raise HTTPException(status_code=400, detail="user_email is required")

    user = get_or_create_user(db, user_email)

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

    await notification_manager.send_task_notification(db_task, "created")
    return db_task


@app.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            return []
        return db.query(Task).filter(Task.user_id == user.id).all()

    return db.query(Task).all()


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_update.dict(exclude_unset=True)
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
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await notification_manager.send_task_notification(task, "deleted")
    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}


@app.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(message: ChatMessage, db: Session = Depends(get_db)):
    if not message.user_email:
        raise HTTPException(status_code=400, detail="user_email is required")

    user = get_or_create_user(db, message.user_email)
    parsed_tasks = task_parser.parse_task_from_text(message.message)

    created_tasks = []
    updated_tasks = []

    for task_data in parsed_tasks:
        db_task = Task(
            title=task_data.title,
            description=task_data.description,
            deadline=task_data.deadline,
            priority=task_data.priority,
            estimated_duration=task_data.estimated_duration,
            category=task_data.category,
            notification_type=task_data.notification_type or "email",
            recipient_email=task_data.recipient_email,
            reminder_minutes_before=task_data.reminder_minutes_before,
            email_sent=False,
            user_id=user.id,
            is_recurring=task_data.is_recurring or False,
            recurring_pattern=task_data.recurring_pattern,
        )
        db.add(db_task)
        created_tasks.append(db_task)

    db.commit()

    for db_task in created_tasks:
        db.refresh(db_task)

    # Create response with refreshed tasks (now includes user_id)
    response_text = generate_ai_response(message.message, created_tasks, message.user_email)

    return ChatResponse(
        response=response_text,
        tasks_created=created_tasks,
        tasks_updated=updated_tasks,
    )


def generate_ai_response(
    user_message: str,
    parsed_tasks: List[TaskCreate],
    user_email: Optional[str] = None,
) -> str:
    if not parsed_tasks:
        return (
            "I didn't detect any specific tasks in your message. "
            "Could you try rephrasing it? For example: "
            "'Remind me to send the project tomorrow'"
        )

    task_count = len(parsed_tasks)

    if task_count == 1:
        task = parsed_tasks[0]
        response = f"I've created the task: '{task.title}'"

        if task.deadline:
            response += f" with deadline {task.deadline.strftime('%B %d at %I:%M %p')}"

        if task.priority and task.priority > 1:
            priority_text = "high" if task.priority == 3 else "medium"
            response += f" and marked it as {priority_text} priority"

        if task.notification_type == "email" and user_email:
            response += f" and I will send an email reminder to {user_email}"
            if task.reminder_minutes_before:
                response += f" {task.reminder_minutes_before} minutes before"

        response += "."
    else:
        response = f"I've created {task_count} tasks for you: "
        task_titles = [f"'{task.title}'" for task in parsed_tasks]
        response += ", ".join(task_titles) + "."

    response += " Is there anything else you'd like me to help you with?"
    return response


@app.get("/schedule")
async def get_schedule(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = get_user_or_404(db, user_email)
        tasks = db.query(Task).filter(Task.user_id == user.id).all()
    else:
        tasks = db.query(Task).all()

    return task_planner.suggest_schedule(tasks)


@app.get("/conflicts")
async def get_conflicts(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = get_user_or_404(db, user_email)
        tasks = db.query(Task).filter(Task.user_id == user.id).all()
    else:
        tasks = db.query(Task).all()

    return task_planner.detect_conflicts(tasks)


@app.post("/auto-reschedule")
async def auto_reschedule(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = get_user_or_404(db, user_email)
        tasks = db.query(Task).filter(Task.user_id == user.id).all()
    else:
        tasks = db.query(Task).all()

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


@app.get("/insights")
async def get_insights(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if user_email:
        user = get_user_or_404(db, user_email)
        tasks = db.query(Task).filter(Task.user_id == user.id).all()
    else:
        tasks = db.query(Task).all()

    return task_planner.get_productivity_insights(tasks)


@app.get("/calendar/status")
async def get_calendar_status():
    return {
        "authenticated": calendar_integration.is_authenticated(),
        "message": (
            "Connected to Google Calendar"
            if calendar_integration.is_authenticated()
            else "Not authenticated"
        ),
    }


@app.get("/calendar/events")
async def get_calendar_events(days_ahead: int = 7):
    if not calendar_integration.is_authenticated():
        return {"error": "Not authenticated with Google Calendar"}

    events = calendar_integration.get_upcoming_events(days_ahead)
    return {"events": events}


@app.post("/calendar/sync")
async def sync_tasks_to_calendar(
    user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if not calendar_integration.is_authenticated():
        return {"error": "Not authenticated with Google Calendar"}

    if user_email:
        user = get_user_or_404(db, user_email)
        tasks = db.query(Task).filter(
            Task.user_id == user.id,
            Task.deadline.isnot(None),
            Task.status != "completed",
        ).all()
    else:
        tasks = db.query(Task).filter(
            Task.deadline.isnot(None),
            Task.status != "completed",
        ).all()

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


@app.get("/calendar/summary")
async def get_calendar_summary(days_ahead: int = 7):
    if not calendar_integration.is_authenticated():
        return {"error": "Not authenticated with Google Calendar"}

    return calendar_integration.get_calendar_summary(days_ahead)


@app.post("/recurring/process")
async def process_recurring_tasks(db: Session = Depends(get_db)):
    """Manually trigger recurring task processing"""
    created_tasks = recurring_task_manager.process_recurring_tasks(db)
    return {
        "message": f"Processed recurring tasks, created {len(created_tasks)} new instances",
        "created_tasks": created_tasks
    }


@app.put("/tasks/{task_id}/complete-recurring")
async def complete_recurring_task(task_id: int, db: Session = Depends(get_db)):
    """Complete a recurring task and create next instance"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    success = recurring_task_manager.mark_instance_completed(db, task)
    
    await notification_manager.send_task_notification(task, "completed")
    
    return {
        "message": "Task completed",
        "next_instance_created": success
    }


@app.post("/meeting/suggest")
async def suggest_meeting_times(request: MeetingRequest):
    """Suggest multiple meeting time options"""
    result = meeting_scheduler.suggest_meeting_times(
        title=request.title,
        duration_hours=request.duration_hours,
        participants=request.participants,
        preferred_days=request.preferred_days,
        preferred_time_start=request.preferred_time_start,
        preferred_time_end=request.preferred_time_end,
        days_ahead=request.days_ahead
    )
    return result


@app.post("/meeting/best")
async def find_best_meeting_time(request: MeetingRequest):
    """Find the single best meeting time with reasoning"""
    result = meeting_scheduler.find_best_meeting_time(
        title=request.title,
        duration_hours=request.duration_hours,
        participants=request.participants,
        urgency=request.urgency
    )
    return result


@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    await websocket_endpoint(websocket, lambda: SessionLocal())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)