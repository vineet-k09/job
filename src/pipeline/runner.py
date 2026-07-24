import contextlib
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from src.config import AppConfig, load_config
from src.db.models import Application, Company, Contact, Email, History, Job, Run
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
        failed_apps = (
            session.query(Application)
            .filter(Application.state.in_(["Failed", "Research Failed", "Draft Failed", "Validation Failed"]))
            .all()
        )

        if not failed_apps:
            logger.info("No failed applications found to retry.")
            session.close()
            return self.run(resume_only=True)

        run_id = generate_run_id(session)
        p_log = PipelineLogger(logger, run_id, "Pipeline Retry")
        p_log.info("Resetting failed applications for retry...")

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
            with contextlib.suppress(Exception):
                session.rollback()
            try:
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
            except Exception as rollback_err:
                with contextlib.suppress(Exception):
                    session.rollback()
                logger.error(f"Failed to save failure state for application {app.id}: {rollback_err}")

    def run_targeted(self, target_input: str, jd: str | None = None, max_stage: int = 12) -> str:
        """
        Executes a targeted search, research, and outreach for a specific company or contact.
        """
        session = self.SessionLocal()
        run_id = generate_run_id(session)

        p_log = PipelineLogger(logger, run_id, "Targeted Outreach Start")
        p_log.info(f"Initializing targeted outreach run: {run_id} for input: '{target_input}'")

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
            # 1. Parse target input using LLM
            prompt = (
                f"Analyze the following targeted outreach input string:\n"
                f"'{target_input}'\n\n"
                f"This input may contain a company name, a domain name, an email address, or a combination. "
                f"Extract and return the cleaned canonical company name, the domain, "
                f"the contact email (if explicitly provided), and the contact name (if deducible)."
            )
            
            from pydantic import BaseModel, Field
            class TargetedParseResponse(BaseModel):
                company_name: str = Field(description="Canonical cleaned company name")
                domain: str | None = Field(description="Company website domain name or null")
                contact_email: str | None = Field(description="Direct contact email address or null")
                contact_name: str | None = Field(description="Deducible contact name or null")

            parsed_target: TargetedParseResponse = self.llm.generate_json(prompt, TargetedParseResponse)  # type: ignore
            
            p_log.info(
                f"Parsed target: Company='{parsed_target.company_name}', Domain='{parsed_target.domain}', "
                f"Email='{parsed_target.contact_email}', Name='{parsed_target.contact_name}'"
            )

            # 2. Get or create Company
            company = session.query(Company).filter(Company.name.ilike(parsed_target.company_name)).first()
            if not company and parsed_target.domain:
                company = session.query(Company).filter(Company.domain == parsed_target.domain.lower()).first()
            
            if not company:
                p_log.info(f"Company '{parsed_target.company_name}' not found in DB. Creating new company entry.")
                company = Company(
                    name=parsed_target.company_name,
                    domain=parsed_target.domain.lower() if parsed_target.domain else None,
                )
                session.add(company)
                session.flush()

            # Temporarily clear exclusions for this targeted company name so it isn't filtered out
            original_exclusions = list(self.config.exclusions.companies)
            self.config.exclusions.companies = [c for c in original_exclusions if c.lower() not in company.name.lower()]

            # 3. Discover jobs specifically for this company (Stage 1 logic) or use pasted JD
            if jd:
                p_log.info("Pasted Job Description provided. Parsing Job details using LLM...")
                import hashlib

                from pydantic import BaseModel, Field
                class JDParseResponse(BaseModel):
                    title: str = Field(description="Title of the job role, e.g. Software Engineer")
                    location: str | None = Field(description="Job location details or Remote")
                    salary: str | None = Field(description="Salary range or details")
                    experience_years: float | None = Field(description="Required experience years if mentioned")
                    description: str = Field(description="Summarized description of key requirements and role responsibilities")

                jd_prompt = (
                    f"Analyze the following pasted job description for a role at {company.name}:\n\n"
                    f"{jd}\n\n"
                    f"Extract the Job Title, Location, Salary details, Required Experience years (float, e.g. 2.5), "
                    f"and a summary of key requirements and responsibilities."
                )
                parsed_jd: JDParseResponse = self.llm.generate_json(jd_prompt, JDParseResponse)  # type: ignore
                
                jd_hash = hashlib.md5(jd.encode('utf-8')).hexdigest()[:8]
                pasted_url = f"pasted://{company.name.lower().replace(' ', '_')}_{jd_hash}"
                
                existing_job = session.query(Job).filter(Job.url == pasted_url).first()
                if not existing_job:
                    p_log.info(f"Creating new Job entry from pasted JD: '{parsed_jd.title}'")
                    new_job = Job(
                        company_id=company.id,
                        title=parsed_jd.title,
                        url=pasted_url,
                        location=parsed_jd.location or (self.config.job_preferences.geographies[0] if self.config.job_preferences.geographies else "Remote"),
                        salary=parsed_jd.salary,
                        experience_years_required=parsed_jd.experience_years,
                        description=parsed_jd.description,
                    )
                    session.add(new_job)
                    session.flush()
                    jobs = [new_job]
                else:
                    p_log.info("Job from pasted JD already exists in database.")
                    jobs = [existing_job]
            else:
                # We can use run_stage_1_job_discovery but we only pass this one company to it
                from src.pipeline.stages import run_stage_1_job_discovery
                jobs = run_stage_1_job_discovery(session, self.config, self.llm, self.browser, [company], run_id)

                # 4. If no jobs found, fallback to creating a speculative job (targeted runs always support this)
                if not jobs:
                    preferred_role = self.config.job_preferences.roles[0] if self.config.job_preferences.roles else "Software Engineer"
                    speculative_job_title = f"{preferred_role} (Targeted Outreach)"
                    p_log.info(f"No jobs found. Creating speculative job: '{speculative_job_title}' for {company.name}")
                    
                    spec_url = f"speculative://{company.name.lower().replace(' ', '_')}"
                    existing_job = session.query(Job).filter(Job.url == spec_url).first()
                    if not existing_job:
                        new_job = Job(
                            company_id=company.id,
                            title=speculative_job_title,
                            url=spec_url,
                            location=self.config.job_preferences.geographies[0] if self.config.job_preferences.geographies else "Remote",
                            description="Targeted outreach software engineering application matching company's tech stack and domain."
                        )
                        session.add(new_job)
                        session.flush()
                        jobs = [new_job]
                    else:
                        jobs = [existing_job]

            # Restore exclusions
            self.config.exclusions.companies = original_exclusions

            # 5. Initialize application & filtering (Stage 2 logic)
            from src.pipeline.stages import run_stage_2_filtering
            active_apps = run_stage_2_filtering(session, self.config, jobs, run_id)

            # 6. If contact email was provided in the input, associate it with the active applications
            if parsed_target.contact_email:
                contact_record = session.query(Contact).filter(Contact.email == parsed_target.contact_email.lower()).first()
                if not contact_record:
                    c_name = parsed_target.contact_name or parsed_target.contact_email.split('@')[0].title()
                    p_log.info(f"Creating new Contact for email: {parsed_target.contact_email}")
                    contact_record = Contact(
                        company_id=company.id,
                        name=c_name,
                        role="Decision Maker",
                        email=parsed_target.contact_email.lower(),
                    )
                    session.add(contact_record)
                    session.flush()
                
                for app in active_apps:
                    app.contact_id = contact_record.id
                    p_log.info(f"Linking contact {contact_record.name} ({contact_record.email}) to Application #{app.id}")
                    session.commit()

            # 7. Process these specific applications
            max_drafts = self.config.pipeline.daily_draft_limit
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
            p_log.info("Targeted pipeline run execution finished.", status="COMPLETED")

        except Exception as e:
            new_run.status = "failed"
            new_run.completed_at = datetime.now(UTC).replace(tzinfo=None)
            session.commit()
            p_log.error(f"Targeted pipeline execution crashed: {e}", status="CRASHED")
            raise e
        finally:
            session.close()

        return run_id
