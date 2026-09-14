import os
import logging
from datetime import datetime, timedelta
from typing import Tuple

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

logger = logging.getLogger(__name__)


class AIEmailGenerator:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if OPENAI_AVAILABLE and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            self.client = None

        if not self.api_key:
            logger.warning("OpenAI API key not found in environment variables")

    def generate_reminder_email(
        self,
        task_title: str,
        deadline: datetime,
        reminder_minutes_before: int,
        task_type: str = "task",
    ) -> Tuple[str, str]:
        """Generate email subject and body using OpenAI"""
        try:
            if not self.client:
                return self._generate_fallback_email(
                    task_title, deadline, reminder_minutes_before, task_type
                )

            reminder_time = deadline - timedelta(minutes=reminder_minutes_before)

            prompt = f"""
Generate a professional reminder email for the following upcoming item.

Task title: {task_title}
Task type: {task_type}
Scheduled time: {deadline.strftime('%A, %B %d, %Y at %I:%M %p')}
Reminder time: {reminder_time.strftime('%A, %B %d, %Y at %I:%M %p')}
Reminder offset: {reminder_minutes_before} minutes before

Requirements:
- Write a concise and professional email.
- Keep the tone friendly and helpful.
- Mention the task title and scheduled time.
- Encourage the user to prepare.
- Keep the body under 120 words.
- Return the result in exactly this format:

SUBJECT: <subject here>
BODY: <body here>
""".strip()

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You generate short, professional reminder emails.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=220,
                temperature=0.5,
            )

            content = response.choices[0].message.content.strip()
            subject, body = self._parse_email_response(content)

            if not subject or not body:
                logger.warning("Failed to parse OpenAI response, using fallback email")
                return self._generate_fallback_email(
                    task_title, deadline, reminder_minutes_before, task_type
                )

            return subject, body

        except Exception as e:
            logger.error(f"Error generating AI email: {e}")
            return self._generate_fallback_email(
                task_title, deadline, reminder_minutes_before, task_type
            )

    def _parse_email_response(self, content: str) -> Tuple[str, str]:
        """Parse SUBJECT/BODY formatted response"""
        subject = ""
        body = ""

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        body_started = False
        body_parts = []

        for line in lines:
            upper_line = line.upper()

            if upper_line.startswith("SUBJECT:"):
                subject = line.split(":", 1)[1].strip()
                body_started = False
            elif upper_line.startswith("BODY:"):
                body_text = line.split(":", 1)[1].strip()
                if body_text:
                    body_parts.append(body_text)
                body_started = True
            elif body_started:
                body_parts.append(line)

        body = " ".join(body_parts).strip()
        return subject, body

    def _generate_fallback_email(
        self,
        task_title: str,
        deadline: datetime,
        reminder_minutes_before: int,
        task_type: str = "task",
    ) -> Tuple[str, str]:
        """Fallback email if OpenAI is unavailable"""
        subject = f"Reminder: {task_title}"

        body = (
            f"Hello,\n\n"
            f"This is a reminder about your upcoming {task_type}: {task_title}.\n"
            f"It is scheduled for {deadline.strftime('%A, %B %d, %Y at %I:%M %p')}.\n"
            f"This reminder is being sent {reminder_minutes_before} minutes in advance.\n\n"
            f"Please make sure you are prepared.\n\n"
            f"Best regards,\n"
            f"Your AI Task Assistant"
        )

        return subject, body


ai_email_generator = AIEmailGenerator()