import os
import smtplib
import logging
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = os.getenv("GMAIL_EMAIL")
        self.sender_password = os.getenv("GMAIL_APP_PASSWORD")


        
    def send_email(self, recipient_email: str, subject: str, body: str) -> bool:
        """Send an email using Gmail SMTP"""
        try:
            print("Sender email:", self.sender_email)
            print("Password exists:", bool(self.sender_password))
            print("Recipient email:", recipient_email)

            if not self.sender_email or not self.sender_password:
                logger.error("Gmail credentials are not configured")
                return False

            if not recipient_email or "@" not in recipient_email:
                logger.error("Recipient email is missing or invalid")
                return False

            if not subject:
                subject = "Reminder"

            if not body:
                body = "This is your reminder."

            message = MIMEMultipart()
            message["From"] = self.sender_email
            message["To"] = recipient_email
            message["Subject"] = subject
            message.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(
                    self.sender_email,
                    recipient_email,
                    message.as_string()
                )

            print("Email was sent successfully.")
            logger.info(f"Email sent successfully to {recipient_email}")
            return True

        except Exception as e:
            print("Email sending error:", str(e))
            logger.error(f"Failed to send email to {recipient_email}: {e}")
            return False

    def test_connection(self) -> bool:
        """Test email service connection"""
        try:
            if not self.sender_email or not self.sender_password:
                logger.error("Gmail credentials are not configured")
                return False

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.sender_email, self.sender_password)

            logger.info("Email service connection test successful")
            return True

        except Exception as e:
            logger.error(f"Email service connection test failed: {e}")
            return False


email_service = EmailService()