import os
import logging
import resend
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY")

        # Resend test sender
        self.sender_email = os.getenv(
            "RESEND_FROM_EMAIL",
            "onboarding@resend.dev"
        )

        if self.api_key:
            resend.api_key = self.api_key


    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str
    ) -> bool:
        """Send an email using Resend API."""

        try:
            logger.info(
                f"Attempting Resend email | "
                f"recipient='{recipient_email}' | "
                f"sender='{self.sender_email}'"
            )

            # Check API key
            if not self.api_key:
                logger.error(
                    "RESEND_API_KEY is not configured."
                )
                return False

            # Check recipient
            if not recipient_email or "@" not in recipient_email:
                logger.error(
                    f"Recipient email is missing or invalid: "
                    f"{recipient_email}"
                )
                return False

            # Default subject
            if not subject:
                subject = "Reminder"

            # Default body
            if not body:
                body = "This is your reminder."

            params = {
                "from": f"Personal Task Assistant <{self.sender_email}>",
                "to": [recipient_email],
                "subject": subject,
                "text": body,
            }

            response = resend.Emails.send(params)

            logger.info(
                f"Email sent successfully with Resend | "
                f"recipient='{recipient_email}' | "
                f"response='{response}'"
            )

            return True

        except Exception as e:
            logger.exception(
                f"Failed to send email with Resend | "
                f"recipient='{recipient_email}' | "
                f"error='{e}'"
            )

            return False


    def test_connection(self) -> bool:
        """
        Check whether Resend API configuration exists.

        Unlike SMTP, Resend does not require opening a persistent
        connection to an email server.
        """

        if not self.api_key:
            logger.error(
                "RESEND_API_KEY is not configured."
            )
            return False

        logger.info(
            "Resend API key is configured."
        )

        return True


email_service = EmailService()