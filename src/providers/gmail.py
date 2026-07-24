import base64
import logging
import mimetypes
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger("recruiting-platform.providers.gmail")


class GmailProvider:
    """
    Gmail API integration using Google API Client and OAuth2.
    """

    def __init__(self, credentials_path: str, token_path: str, scopes: list[str]):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.scopes = scopes
        self.creds: Credentials | None = None
        self.service = None

    def authenticate(self, interactive: bool = True) -> bool:
        """
        Authenticates with Gmail API. Reuses existing token if valid.
        If interactive is True, opens a browser to authenticate.
        """
        if os.path.exists(self.token_path):
            try:
                self.creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
                    self.token_path, self.scopes
                )
            except Exception as e:
                logger.warning(f"Failed to load token file: {e}. Re-authenticating.")

        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())  # type: ignore[no-untyped-call]
                    with open(self.token_path, "w") as token:
                        token.write(self.creds.to_json())  # type: ignore[no-untyped-call]
                    logger.info("Successfully refreshed Gmail token.")
                except Exception as e:
                    logger.error(f"Failed to refresh Gmail token: {e}")
                    self.creds = None

            if not self.creds:
                if not os.path.exists(self.credentials_path):
                    logger.warning(
                        f"Gmail OAuth client secrets file not found at {self.credentials_path}. "
                        "Gmail draft creation will fail until credentials.json is provided. "
                        "Please download it from the Google Cloud Console."
                    )
                    return False

                if not interactive:
                    logger.error("Gmail authorization required but running in non-interactive mode.")
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.scopes)
                    self.creds = flow.run_local_server(port=8080)
                    # Save the credentials for the next run
                    with open(self.token_path, "w") as token:
                        token.write(self.creds.to_json())
                    logger.info("Successfully authenticated Gmail and saved credentials.")
                except Exception as e:
                    logger.error(f"Gmail OAuth flow failed: {e}")
                    return False

        if self.creds and self.creds.valid:
            self.service = build("gmail", "v1", credentials=self.creds)
            return True

        return False

    def create_draft(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        resume_path: str | None = None,
    ) -> str:
        """
        Creates a draft email in the user's Gmail account.
        Attaches the resume if resume_path is provided.
        Returns the Draft ID.
        """
        if not self.service:
            # Try to authenticate silently
            if not self.authenticate(interactive=False):
                raise RuntimeError("Gmail service not authenticated. Cannot create draft.")

        message = MIMEMultipart()
        message["to"] = to_email
        message["subject"] = subject

        # Add HTML body
        msg_body = MIMEText(body_html, "html")
        message.attach(msg_body)

        # Attach resume if provided and exists
        if resume_path and os.path.exists(resume_path):
            filename = os.path.basename(resume_path)
            content_type, encoding = mimetypes.guess_type(resume_path)
            if content_type is None or encoding is not None:
                content_type = "application/octet-stream"
            main_type, sub_type = content_type.split("/", 1)

            try:
                with open(resume_path, "rb") as fp:
                    attachment = MIMEBase(main_type, sub_type)
                    attachment.set_payload(fp.read())
                encoders.encode_base64(attachment)
                attachment.add_header("Content-Disposition", "attachment", filename=filename)
                message.attach(attachment)
                logger.info(f"Attached resume {filename} to draft message.")
            except Exception as e:
                logger.error(f"Failed to attach resume file {resume_path}: {e}")

        # Encode raw MIME string
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        try:
            draft_body = {"message": {"raw": raw_message}}
            assert self.service is not None
            draft = self.service.users().drafts().create(userId="me", body=draft_body).execute()
            logger.info(f"Created draft successfully. Draft ID: {draft['id']}")
            return str(draft["id"])
        except Exception as e:
            logger.error(f"Failed to create Gmail draft: {e}")
            raise RuntimeError(f"Gmail draft creation failed: {e}") from e

    def send_draft(self, draft_id: str) -> None:
        """
        Sends an existing Gmail draft by its draft ID.
        """
        if not self.service:
            # Try to authenticate silently
            if not self.authenticate(interactive=False):
                raise RuntimeError("Gmail service not authenticated. Cannot send draft.")
        try:
            assert self.service is not None
            self.service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
            logger.info(f"Sent draft successfully. Draft ID: {draft_id}")
        except Exception as e:
            logger.error(f"Failed to send Gmail draft {draft_id}: {e}")
            raise RuntimeError(f"Gmail draft send failed: {e}") from e
