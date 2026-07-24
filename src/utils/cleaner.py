import logging
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import Application, Contact
from src.db.session import get_session_factory
from src.utils.email_verifier import verify_email

logger = logging.getLogger("recruiting-platform.utils.cleaner")


def clean_invalid_emails_and_states(db_path: str = "data/platform.db") -> dict[str, Any]:
    """
    Cleans invalid/non-existent email addresses from contacts and updates broken application states.
    
    CRITICAL SAFETY GUARANTEE:
    This function NEVER deletes any records from `companies`, `jobs`, `contacts`, or `emails` tables.
    It only clears invalid email fields and normalizes application states.
    """
    session_factory = get_session_factory(db_path)
    session: Session = session_factory()

    cleared_emails_count = 0
    updated_applications_count = 0

    try:
        # 1. Clean invalid contact emails
        contacts_with_email = session.query(Contact).filter(Contact.email.isnot(None), Contact.email != "").all()
        for contact in contacts_with_email:
            if not contact.email:
                continue
            is_valid, reason = verify_email(contact.email)
            if not is_valid:
                logger.warning(
                    f"Clearing invalid contact email '{contact.email}' for Contact #{contact.id} "
                    f"({contact.name} @ {contact.company.name if contact.company else 'Unknown'}). Reason: {reason}"
                )
                contact.email = None
                cleared_emails_count += 1

                # Update associated applications
                assoc_apps = session.query(Application).filter(Application.contact_id == contact.id).all()
                for app in assoc_apps:
                    if app.state in ("Professional Email Discovery", "Email Discovery", "Draft Failed"):
                        app.state = "No Professional Email"
                        updated_applications_count += 1

        # 2. Clean applications stuck in broken/failed states where email is missing
        failed_apps = (
            session.query(Application)
            .filter(Application.state.in_(["Research Failed", "Draft Failed", "Validation Failed"]))
            .all()
        )
        for app in failed_apps:
            # If app contact has no valid email, mark as No Professional Email cleanly
            if not app.contact or not app.contact.email:
                app.state = "No Professional Email"
                updated_applications_count += 1

        session.commit()

        summary = {
            "cleared_emails_count": cleared_emails_count,
            "updated_applications_count": updated_applications_count,
            "message": (
                f"Cleaning complete. Cleared {cleared_emails_count} invalid emails, "
                f"updated {updated_applications_count} application states. ZERO records were deleted."
            ),
        }
        logger.info(summary["message"])
        return summary
    except Exception as e:
        session.rollback()
        logger.error(f"Error during email & state cleanup: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    res = clean_invalid_emails_and_states()
    print(res)
