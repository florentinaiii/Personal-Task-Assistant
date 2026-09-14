import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from models import Task
from email_service import email_service
from ai_email_generator import ai_email_generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.is_running = False
        self.check_interval = 60
        self.sent_reminders: Dict[int, set] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New connection. Total connections: {len(self.active_connections)}")

        await self.send_personal_message(
            {
                "type": "welcome",
                "message": "Connected to notification system",
            },
            websocket,
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Connection closed. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict):
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)

    async def start_background_tasks(self, db_session_factory):
        if not self.is_running:
            self.is_running = True
            asyncio.create_task(self.check_reminders(db_session_factory))
            logger.info("Background reminder checker started")

    async def check_reminders(self, db_session_factory):
        while self.is_running:
            db = None
            try:
                db = db_session_factory()
                now = datetime.now()

                await self._check_email_reminders(db, now)

                upcoming_tasks = self._get_upcoming_reminders(db, now)
                for task, reminder_type in upcoming_tasks:
                    await self.send_task_reminder(task, reminder_type)

            except Exception as e:
                logger.error(f"Error checking reminders: {e}")

            finally:
                if db:
                    db.close()

            await asyncio.sleep(self.check_interval)

    def _get_upcoming_reminders(self, db: Session, now: datetime) -> List[tuple]:
        upcoming_tasks = []

        tasks = db.query(Task).filter(
            Task.deadline.isnot(None),
            Task.status != "completed"
        ).all()

        for task in tasks:
            if not task.deadline:
                continue

            if task.id not in self.sent_reminders:
                self.sent_reminders[task.id] = set()

            time_until_deadline = task.deadline - now
            reminder_type = None

            if timedelta(minutes=59) < time_until_deadline <= timedelta(hours=1):
                reminder_type = "1_hour"
            elif timedelta(hours=23) < time_until_deadline <= timedelta(hours=24):
                reminder_type = "24_hours"
            elif timedelta(minutes=29) < time_until_deadline <= timedelta(minutes=30):
                reminder_type = "30_minutes"
            elif -timedelta(hours=1) < time_until_deadline <= timedelta(seconds=0):
                reminder_type = "overdue"

            if reminder_type and reminder_type not in self.sent_reminders[task.id]:
                upcoming_tasks.append((task, reminder_type))

        return upcoming_tasks

    async def send_task_reminder(self, task: Task, reminder_type: str):
        reminder_messages = {
            "1_hour": f"Reminder: Task '{task.title}' is due in 1 hour!",
            "24_hours": f"Heads up: Task '{task.title}' is due tomorrow!",
            "30_minutes": f"Urgent: Task '{task.title}' is due in 30 minutes!",
            "overdue": f"Overdue: Task '{task.title}' was due at {task.deadline.strftime('%I:%M %p')}",
        }

        message = {
            "type": "reminder",
            "task_id": task.id,
            "task_title": task.title,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "priority": task.priority,
            "reminder_type": reminder_type,
            "message": reminder_messages.get(reminder_type, f"Reminder for {task.title}"),
            "timestamp": datetime.now().isoformat(),
        }

        await self.broadcast(message)

        if task.id in self.sent_reminders:
            self.sent_reminders[task.id].add(reminder_type)

        logger.info(f"Sent {reminder_type} websocket reminder for task: {task.title}")

    async def send_task_notification(self, task: Task, notification_type: str, message: str = None):
        notification_messages = {
            "created": f"New task created: '{task.title}'",
            "updated": f"Task updated: '{task.title}'",
            "completed": f"Task completed: '{task.title}' 🎉",
            "deleted": f"Task deleted: '{task.title}'",
        }

        notification_message = message or notification_messages.get(
            notification_type,
            f"Task {notification_type}: {task.title}",
        )

        message_data = {
            "type": "task_notification",
            "task_id": task.id,
            "task_title": task.title,
            "notification_type": notification_type,
            "message": notification_message,
            "timestamp": datetime.now().isoformat(),
        }

        await self.broadcast(message_data)
        logger.info(f"Sent {notification_type} notification for task: {task.title}")

    async def send_schedule_update(self, schedule_data: Dict):
        message = {
            "type": "schedule_update",
            "schedule": schedule_data,
            "message": "Your schedule has been updated",
            "timestamp": datetime.now().isoformat(),
        }
        await self.broadcast(message)

    async def send_conflict_alert(self, conflicts: List[Dict]):
        message = {
            "type": "conflict_alert",
            "conflicts": conflicts,
            "message": f"Scheduling conflicts detected: {len(conflicts)} issues found",
            "timestamp": datetime.now().isoformat(),
        }
        await self.broadcast(message)

    async def send_calendar_sync_result(self, sync_result: Dict):
        message = {
            "type": "calendar_sync",
            "result": sync_result,
            "message": f"Calendar sync completed: {len(sync_result.get('synced', []))} tasks synced",
            "timestamp": datetime.now().isoformat(),
        }
        await self.broadcast(message)

    async def _check_email_reminders(self, db: Session, now: datetime):
        """Check for email reminders that need to be sent"""
        # Get tasks that need email reminders
        email_tasks = db.query(Task).filter(
            Task.notification_type == "email",
            Task.reminder_minutes_before.isnot(None),
            Task.deadline.isnot(None),
            Task.email_sent.is_(False),
            Task.status != "completed"
        ).all()
        
        for task in email_tasks:
            # Calculate reminder trigger time
            reminder_time = task.deadline - timedelta(minutes=task.reminder_minutes_before)
            
            logger.info(
                f"Checking email reminder | task='{task.title}' | "
                f"user_email='{task.user.email if task.user else 'unknown'}' | "
                f"deadline='{task.deadline}' | "
                f"reminder_time='{reminder_time}' | "
                f"now='{now}'"
            )
            
            # Wider window: 2 minutes before to 5 minutes after
            if reminder_time - timedelta(minutes=2) <= now <= reminder_time + timedelta(minutes=5):
                success = await self._send_email_reminder(task)
                
                if success:
                    # Mark email as sent
                    task.email_sent = True
                    db.commit()
                    logger.info(f"Email reminder sent successfully for task: {task.title}")
                else:
                    logger.error(f"Failed to send email reminder for task: {task.title}")

    async def _send_email_reminder(self, task: Task) -> bool:
        try:
            logger.info(f"Generating AI email for task: {task.title}")

            if not task.user or not task.user.email:
                logger.error(f"No user email available for task: {task.title}")
                return False

            recipient = task.user.email

            subject, body = ai_email_generator.generate_reminder_email(
                task_title=task.title,
                deadline=task.deadline,
                reminder_minutes_before=task.reminder_minutes_before,
                task_type=task.category or "task",
            )

            logger.info(
                f"Sending email reminder | task='{task.title}' | "
                f"to='{recipient}' | subject='{subject}'"
            )

            success = email_service.send_email(
                recipient_email=recipient,
                subject=subject,
                body=body,
            )

            return success

        except Exception as e:
            logger.error(f"Error sending email reminder for task '{task.title}': {e}")
            return False


notification_manager = NotificationManager()


async def websocket_endpoint(websocket: WebSocket, db_session_factory):
    await notification_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await notification_manager.send_personal_message({"type": "pong"}, websocket)
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        notification_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        notification_manager.disconnect(websocket)