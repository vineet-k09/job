from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from src.config import AppConfig, load_config
from src.db.models import Application, Email, History, Run
from src.db.session import get_session_factory, init_db

# Import stage functions
from src.pipeline.stages import (
    run_stage_0_company_discovery,
    run_stage_1_job_discovery,
    run_stage_2_filtering,
    run_stage_3_company_research,
    run_stage_4_contact_research,
    run_stage_5_email_discovery,
    run_stage_6_opportunity_scoring,
    run_stage_7_resume_tailoring,
    run_stage_8_email_generation,
    run_stage_9_validation,
    run_stage_10_gmail_draft_creation,
    run_stage_11_database_finalization,
)
from src.providers.browser import BrowserProvider
from src.providers.gmail import GmailProvider
from src.providers.llm import get_llm_provider
from src.utils.logging import PipelineLogger, get_logger

logger = get_logger("recruiting-platform.pipeline.runner")


def generate_run_id(session: Session) -> str:
    """
    Generates a unique Run ID: RUN-YYYYMMDD-NNN.
    """
    today_str = datetime.now(UTC).strftime("%Y%m%d")
    prefix = f"RUN-{today_str}-"

    existing_runs = session.query(Run).filter(Run.id.like(f"{prefix}%")).order_by(Run.id.desc()).all()

    if not existing_runs:
        return f"{prefix}001"

    last_run_id = existing_runs[0].id
    try:
        suffix = int(last_run_id.split("-")[-1])
        new_suffix = f"{suffix + 1:03d}"
    except ValueError:
        new_suffix = "001"

    return f"{prefix}{new_suffix}"


class PipelineRunner:
    """
    Orchestrates the entire recruiting pipeline.
    """

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: AppConfig = load_config(config_path)
        init_db(self.config.pipeline.db_path)
        self.SessionLocal = get_session_factory(self.config.pipeline.db_path)

        # Initialize providers
        self.llm = get_llm_provider(self.config.llm)
        self.browser = BrowserProvider()
        self.gmail = GmailProvider(
            credentials_path=self.config.gmail.credentials_file,
            token_path=self.config.gmail.token_file,
            scopes=self.config.gmail.scopes,
        )

    def get_todays_draft_count(self, session: Session) -> int:
        """
        Count draft emails successfully created in Gmail today.
        """
        today_start = datetime.combine(date.today(), datetime.min.time())
        count = session.query(Email).filter(Email.status == "draft_created", Email.created_at >= today_start).count()
        return count

    def run(
        self,
        resume_only: bool = False,
        max_stage: int = 12,
        limit_drafts: int | None = None,
    ) -> str:
        """
        Executes the pipeline runner.
        - Checks for interrupted/paused applications and resumes them.
        - If none (and resume_only is False), discovers new companies/jobs and runs them.
        - Enforces daily draft limits.
        """
        session = self.SessionLocal()
        run_id = generate_run_id(session)

        p_log = PipelineLogger(logger, run_id, "Pipeline Run Start")
        p_log.info(f"Initializing pipeline run: {run_id} (Up to Stage {max_stage})")

        new_run = Run(id=run_id, status="running")
        session.add(new_run)
        session.commit()

        if max_stage >= 10:
            import sys
            interactive = sys.stdout.isatty()
            p_log.info("Checking Gmail API credentials...")
            if not self.gmail.authenticate(interactive=interactive):
                p_log.warning("Gmail API authentication failed. Draft creation stages will be skipped/paused.")

        try:
            terminal_states = [
                "Completed",
                "Skipped",
                "Duplicate",
                "Salary Too Low",
                "Excluded Company",
                "Ghost Job",
                "No Professional Email",
                "Research Failed",
                "Timeout",
                "Validation Failed",
                "Draft Failed",
                "Manual Skip",
                "Failed",
            ]

            active_apps = session.query(Application).filter(Application.state.notin_(terminal_states)).all()

            if active_apps:
                p_log.info(f"Resuming {len(active_apps)} interrupted applications...")
            elif resume_only:
                p_log.info("No active applications to resume. (resume_only = True)")
                new_run.status = "completed"
                new_run.completed_at = datetime.utcnow()
                session.commit()
                return run_id
            else:
                p_log.info("No interrupted applications found. Running fresh discovery...")
                # Stage 0: Company Discovery
                companies = run_stage_0_company_discovery(session, self.config, self.llm, self.browser, run_id)
                # Stage 1: Job Discovery
                jobs = run_stage_1_job_discovery(session, self.config, self.llm, self.browser, companies, run_id)
                # Stage 2: Filtering
                active_apps = run_stage_2_filtering(session, self.config, jobs, run_id)

            max_drafts = limit_drafts or self.config.pipeline.daily_draft_limit

            for app in active_apps:
                current_drafts = self.get_todays_draft_count(session)
                if current_drafts >= max_drafts and app.current_stage == 10:
                    p_log.warning(
                        f"Daily draft limit of {max_drafts} reached. "
                        f"Skipping further draft creation today. Application #{app.id} paused.",
                        status="PAUSED",
                    )
                    break

                self._process_application(session, app, run_id, max_stage)

            new_run.status = "completed"
            new_run.completed_at = datetime.now(UTC).replace(tzinfo=None)
            session.commit()
            p_log.info("Pipeline run execution finished.", status="COMPLETED")

        except Exception as e:
            new_run.status = "failed"
            new_run.completed_at = datetime.now(UTC).replace(tzinfo=None)
            session.commit()
            p_log.error(f"Pipeline execution crashed: {e}", status="CRASHED")
            raise e
        finally:
            session.close()

        return run_id

    def retry_failed(self) -> str:
        """
        Resets failed applications back to their preceding active stage,
        then executes the pipeline runner to retry them.
        """
        session = self.SessionLocal()
        run_id = generate_run_id(session)
        p_log = PipelineLogger(logger, run_id, "Pipeline Retry")
        p_log.info("Resetting failed applications for retry...")

        new_run = Run(id=run_id, status="running")
        session.add(new_run)
        session.commit()

        failed_apps = (
            session.query(Application)
            .filter(Application.state.in_(["Failed", "Research Failed", "Draft Failed", "Validation Failed"]))
            .all()
        )

        if not failed_apps:
            p_log.info("No failed applications found to retry.")
            session.close()
            return self.run(resume_only=True)

        for app in failed_apps:
            old_state = app.state
            if old_state == "Research Failed":
                app.current_stage = 3
                app.state = "Company Research"
            elif old_state == "Draft Failed":
                app.current_stage = 10
                app.state = "Gmail Draft Creation"
            elif old_state == "Validation Failed":
                app.current_stage = 7
                app.state = "Resume Tailoring"
            else:
                # Default fallback: resume tailoring
                app.current_stage = 7
                app.state = "Resume Tailoring"

            session.add(
                History(
                    application_id=app.id,
                    stage=app.current_stage,
                    state=app.state,
                    run_id=run_id,
                    notes=f"Reset state from '{old_state}' to retry processing.",
                )
            )
            p_log.info(f"Reset Application #{app.id} state to '{app.state}' for retry.")

        new_run.status = "completed"
        new_run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()
        session.close()

        # Run normal pipeline to process the reset applications
        return self.run(resume_only=True)

    def _process_application(self, session: Session, app: Application, run_id: str, max_stage: int = 12) -> None:
        """
        Drives a single Application forward through the stages, up to max_stage.
        """
        company = app.job.company
        p_log = PipelineLogger(logger, run_id, f"App #{app.id} processing", company.name)

        try:
            # Stage 3: Company Research
            if app.current_stage == 3 and max_stage >= 3:
                success = run_stage_3_company_research(session, self.config, self.llm, self.browser, app, run_id)
                if not success:
                    return

            # Stage 4: Contact Research
            if app.current_stage == 4 and max_stage >= 4:
                success = run_stage_4_contact_research(session, self.config, self.llm, self.browser, app, run_id)
                if not success:
                    return

            # Stage 5: Professional Email Discovery
            if app.current_stage == 5 and max_stage >= 5:
                success = run_stage_5_email_discovery(session, self.config, self.llm, self.browser, app, run_id)
                if not success:
                    return

            # Stage 6: Opportunity Scoring
            if app.current_stage == 6 and max_stage >= 6:
                success = run_stage_6_opportunity_scoring(session, self.config, self.llm, app, run_id)
                if not success:
                    return

            # Stage 7: Resume Tailoring
            if app.current_stage == 7 and max_stage >= 7:
                success = run_stage_7_resume_tailoring(session, self.config, self.llm, app, run_id)
                if not success:
                    return

            # Stage 8: Email Generation
            if app.current_stage == 8 and max_stage >= 8:
                success = run_stage_8_email_generation(session, self.config, self.llm, app, run_id)
                if not success:
                    return

            # Stage 9: Validation
            if app.current_stage == 9 and max_stage >= 9:
                success = run_stage_9_validation(session, self.config, self.llm, app, run_id)
                if not success:
                    return

            # Stage 10: Gmail Draft Creation
            if app.current_stage == 10 and max_stage >= 10:
                success = run_stage_10_gmail_draft_creation(session, self.gmail, app, run_id)
                if not success:
                    return

            # Stage 11: Database Finalization
            if app.current_stage == 11 and max_stage >= 11:
                success = run_stage_11_database_finalization(session, app, run_id)
                if not success:
                    return

        except Exception as e:
            p_log.error(f"Error processing application {app.id}: {e}")
            app.state = "Failed"
            session.add(
                History(
                    application_id=app.id,
                    stage=app.current_stage,
                    state="Failed",
                    run_id=run_id,
                    notes=f"Exception encountered during processing: {e}",
                )
            )
            session.commit()
