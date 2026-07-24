import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import Application, Email
from src.db.session import get_session_factory

logger = logging.getLogger("recruiting-platform.utils.exporter")


def export_outreach_data(
    db_path: str = "data/platform.db",
    export_dir: str = "exports",
    export_all: bool = False,
) -> dict[str, Any]:
    """
    Incrementally exports job outreach records (Company info + Contact/Email info) to JSON & CSV files.
    
    Uses `exports/.export_manifest.json` to keep track of already exported application IDs
    so subsequent runs export ONLY new incremental records, preventing duplicate exports
    and minimizing DB overhead.
    """
    out_dir = Path(export_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / ".export_manifest.json"
    exported_ids: set[int] = set()

    if manifest_path.exists() and not export_all:
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest_data = json.load(f)
                exported_ids = set(manifest_data.get("exported_application_ids", []))
        except Exception as e:
            logger.warning(f"Could not load export manifest: {e}")

    session_factory = get_session_factory(db_path)
    session: Session = session_factory()

    try:
        # Query applications that have reached email generation / completed stage or have emails
        apps = (
            session.query(Application)
            .order_by(Application.updated_at.asc())
            .all()
        )

        records_to_export = []
        new_exported_ids = set(exported_ids)

        for app in apps:
            if not export_all and app.id in exported_ids:
                continue

            # Check for associated email
            email_obj = (
                session.query(Email)
                .filter(Email.application_id == app.id)
                .order_by(Email.id.desc())
                .first()
            )

            comp = app.job.company if app.job else None
            contact = app.contact

            record = {
                "application_id": app.id,
                "run_id": app.run_id,
                "company_name": comp.name if comp else "N/A",
                "company_domain": comp.domain if comp else "N/A",
                "company_industry": comp.industry if comp else "N/A",
                "company_employee_count": comp.employee_count if comp else "N/A",
                "job_title": app.job.title if app.job else "N/A",
                "job_location": app.job.location if app.job else "N/A",
                "job_salary": app.job.salary if app.job else "N/A",
                "contact_name": contact.name if contact else "N/A",
                "contact_role": contact.role if contact else "N/A",
                "contact_email": contact.email if (contact and contact.email) else "N/A",
                "email_subject": email_obj.subject if email_obj else "N/A",
                "email_body_preview": (email_obj.body[:300] + "...") if (email_obj and email_obj.body) else "N/A",
                "gmail_draft_id": email_obj.gmail_draft_id if (email_obj and email_obj.gmail_draft_id) else "N/A",
                "application_state": app.state,
                "current_stage": app.current_stage,
                "score": round(app.score, 2) if app.score else None,
                "updated_at": app.updated_at.strftime("%Y-%m-%d %H:%M:%S") if app.updated_at else "N/A",
            }

            records_to_export.append(record)
            new_exported_ids.add(app.id)

        if not records_to_export:
            logger.info("No new records to export. Export manifest is up to date.")
            return {
                "exported_count": 0,
                "total_exported_so_far": len(exported_ids),
                "message": "Incremental export skipped: No new records to export.",
            }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = out_dir / f"job_outreach_export_{timestamp}.json"
        csv_filename = out_dir / f"job_outreach_export_{timestamp}.csv"
        latest_csv_filename = out_dir / "job_outreach_export_latest.csv"

        # Write timestamped JSON
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(records_to_export, f, indent=2)

        # Write CSV
        fieldnames = list(records_to_export[0].keys())
        with open(csv_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records_to_export)

        # Update cumulative latest CSV file
        all_records = []
        for app in apps:
            if app.id in new_exported_ids:
                email_obj = session.query(Email).filter(Email.application_id == app.id).order_by(Email.id.desc()).first()
                comp = app.job.company if app.job else None
                contact = app.contact
                all_records.append({
                    "application_id": app.id,
                    "run_id": app.run_id,
                    "company_name": comp.name if comp else "N/A",
                    "company_domain": comp.domain if comp else "N/A",
                    "company_industry": comp.industry if comp else "N/A",
                    "company_employee_count": comp.employee_count if comp else "N/A",
                    "job_title": app.job.title if app.job else "N/A",
                    "job_location": app.job.location if app.job else "N/A",
                    "job_salary": app.job.salary if app.job else "N/A",
                    "contact_name": contact.name if contact else "N/A",
                    "contact_role": contact.role if contact else "N/A",
                    "contact_email": contact.email if (contact and contact.email) else "N/A",
                    "email_subject": email_obj.subject if email_obj else "N/A",
                    "email_body_preview": (email_obj.body[:300] + "...") if (email_obj and email_obj.body) else "N/A",
                    "gmail_draft_id": email_obj.gmail_draft_id if (email_obj and email_obj.gmail_draft_id) else "N/A",
                    "application_state": app.state,
                    "current_stage": app.current_stage,
                    "score": round(app.score, 2) if app.score else None,
                    "updated_at": app.updated_at.strftime("%Y-%m-%d %H:%M:%S") if app.updated_at else "N/A",
                })

        with open(latest_csv_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_records)

        # Update export manifest JSON
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "last_export_timestamp": datetime.now().isoformat(),
                    "exported_application_ids": list(new_exported_ids),
                },
                f,
                indent=2,
            )

        summary = {
            "exported_count": len(records_to_export),
            "total_exported_so_far": len(new_exported_ids),
            "json_path": str(json_filename),
            "csv_path": str(csv_filename),
            "latest_csv_path": str(latest_csv_filename),
            "message": f"Successfully incrementally exported {len(records_to_export)} new outreach records.",
        }
        logger.info(summary["message"])
        return summary
    finally:
        session.close()


if __name__ == "__main__":
    res = export_outreach_data()
    print(res)
