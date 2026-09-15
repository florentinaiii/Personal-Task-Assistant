import os
import logging

import sib_api_v3_sdk
from dotenv import load_dotenv
from sib_api_v3_sdk.rest import ApiException


load_dotenv()

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        # Brevo configuration
        self.api_key = os.getenv("BREVO_API_KEY")
        self.sender_email = os.getenv(
            "BREVO_SENDER_EMAIL",
            "ibrahimitinaa@gmail.com"
        )
        self.sender_name = os.getenv(
            "BREVO_SENDER_NAME",
            "Personal Task Assistant"
        )

        self.api_instance = None

        if self.api_key:
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key["api-key"] = self.api_key

            api_client = sib_api_v3_sdk.ApiClient(configuration)

            self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                api_client
            )

            logger.info("Brevo email service initialized successfully.")
        else:
            logger.warning(
                "BREVO_API_KEY is not configured."
            )


    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str
    ) -> bool:
        """
        Send a transactional email using the Brevo API.
        """

        try:
            # Check Brevo API configuration
            if not self.api_key:
                logger.error(
                    "Cannot send email: BREVO_API_KEY is not configured."
                )
                return False

            if not self.api_instance:
                logger.error(
                    "Cannot send email: Brevo API client is not initialized."
                )
                return False

            # Validate sender
            if not self.sender_email or "@" not in self.sender_email:
                logger.error(
                    f"Invalid sender email: {self.sender_email}"
                )
                return False

            # Validate recipient
            if not recipient_email or "@" not in recipient_email:
                logger.error(
                    f"Invalid recipient email: {recipient_email}"
                )
                return False

            # Default content
            if not subject:
                subject = "Reminder"

            if not body:
                body = "This is your reminder."

            logger.info(
                f"Attempting Brevo email | "
                f"recipient='{recipient_email}' | "
                f"sender='{self.sender_email}' | "
                f"subject='{subject}'"
            )

            # Sender information
            sender = {
                "name": self.sender_name,
                "email": self.sender_email
            }

            # Recipient information
            recipient = {
                "email": recipient_email
            }

            # Create transactional email
            send_email = sib_api_v3_sdk.SendSmtpEmail(
                sender=sender,
                to=[recipient],
                subject=subject,
                text_content=body
            )

            # Send through Brevo API
            response = self.api_instance.send_transac_email(
                send_email
            )

            message_id = getattr(
                response,
                "message_id",
                None
            )

            logger.info(
                f"Email sent successfully with Brevo | "
                f"recipient='{recipient_email}' | "
                f"message_id='{message_id}'"
            )

            return True

        except ApiException as e:
            logger.error(
                f"Brevo API error | "
                f"recipient='{recipient_email}' | "
                f"status='{getattr(e, 'status', None)}' | "
                f"reason='{getattr(e, 'reason', None)}' | "
                f"body='{getattr(e, 'body', None)}'"
            )

            return False

        except Exception as e:
            logger.exception(
                f"Failed to send email with Brevo | "
                f"recipient='{recipient_email}' | "
                f"error='{e}'"
            )

            return False


    def test_connection(self) -> bool:
        """
        Check whether the Brevo email service is configured.
        """

        if not self.api_key:
            logger.error(
                "BREVO_API_KEY is not configured."
            )
            return False

        if not self.sender_email:
            logger.error(
                "BREVO_SENDER_EMAIL is not configured."
            )
            return False

        if not self.api_instance:
            logger.error(
                "Brevo API client is not initialized."
            )
            return False

        logger.info(
            f"Brevo email service configured | "
            f"sender='{self.sender_email}'"
        )

        return True


email_service = EmailService()