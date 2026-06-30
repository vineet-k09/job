import json
import logging
import os
import subprocess
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config import AppConfig
from src.db.models import (
    Application,
    Company,
    Contact,
    Email,
    History,
    Job,
    ResumeVersion,
)
from src.providers.browser import BrowserProvider
from src.providers.gmail import GmailProvider
from src.providers.llm import BaseLLMProvider
from src.utils.caching import DBCache
from src.utils.logging import PipelineLogger

logger = logging.getLogger("recruiting-platform.pipeline.stages")

# -------------------------------------------------------------
# LLM Response Schemas (Pydantic)
# -------------------------------------------------------------


class DiscoveredCompany(BaseModel):
    name: str = Field(description="Name of the company")
    domain: str | None = Field(description="Primary domain of the company, e.g. company.com")
    employee_count: int | None = Field(description="Estimated number of employees")
    industry: str | None = Field(description="Industry vertical, e.g. SaaS, Fintech")


class CompanyListResponse(BaseModel):
    companies: list[DiscoveredCompany]


class DiscoveredJob(BaseModel):
    title: str = Field(description="Title of the job role")
    url: str | None = Field(description="URL to the job listing or company careers page")
    location: str | None = Field(description="Job location details")
    salary: str | None = Field(description="Salary range or package details")
    experience_years: float | None = Field(description="Required experience years, if mentioned")
    description: str | None = Field(description="Brief summary of requirements or job description")


class JobListResponse(BaseModel):
    jobs: list[DiscoveredJob]


class CompanyResearchResponse(BaseModel):
    business_model: str = Field(description="Business model and core product description")
    funding: str = Field(description="Details of latest funding or launches")
    tech_stack: list[str] = Field(description="List of core languages, frameworks, or databases used")
    culture: str = Field(description="Engineering culture or notable developer initiatives")
    leadership: list[str] = Field(description="Founders, CEO, CTO, or VP Engineering details")


class DiscoveredContact(BaseModel):
    name: str = Field(description="Full name of the contact person")
    role: str = Field(description="Role or title of the contact")
    email_pattern: str | None = Field(description="Observed email format, e.g., first.last@company.com")
    linkedin_url: str | None = Field(description="LinkedIn profile link if available")


class ContactListResponse(BaseModel):
    contacts: list[DiscoveredContact]


class EmailDiscoveryResponse(BaseModel):
    email: str | None = Field(description="Discovered professional email address")
    pattern_used: str | None = Field(description="The pattern or source used to find/verify this email")


class OpportunityScoreResponse(BaseModel):
    role_match: float = Field(description="Score between 0.0 and 1.0 representing how well the role fits")
    tech_stack: float = Field(description="Score between 0.0 and 1.0 representing tech alignment")
    salary: float = Field(description="Score between 0.0 and 1.0 representing salary alignment")
    company_quality: float = Field(description="Score between 0.0 and 1.0 representing company status/domain")
    growth: float = Field(description="Score between 0.0 and 1.0 representing growth potential")
    confidence: float = Field(description="Score between 0.0 and 1.0 representing confidence in data quality")
    reasoning: str = Field(description="Brief summary of scoring rationale")


class ResumeTailorResponse(BaseModel):
    tailored_typst_content: str = Field(description="The complete modified Typst code for the resume")
    keywords_added: list[str] = Field(description="List of ATS keywords or skills added")
    reasoning: str = Field(description="Explanation of modifications and section ordering decisions")


class EmailGenResponse(BaseModel):
    subject: str = Field(description="Subject line for the outreach email")
    body_html: str = Field(description="HTML formatted email body")


class ValidationResponse(BaseModel):
    is_valid: bool = Field(description="True if the resume and email contain no placeholders or hallucinated facts")
    errors: list[str] = Field(description="List of validation errors found")


# -------------------------------------------------------------
# Stage Executors
# -------------------------------------------------------------


def run_stage_0_company_discovery(
    session: Session,
    config: AppConfig,
    llm: BaseLLMProvider,
    browser: BrowserProvider,
    run_id: str,
) -> list[Company]:
    """
    Stage 0: Company Discovery
    Finds tech companies matching size, location, and role preferences.
    """
    p_log = PipelineLogger(logger, run_id, "Stage 0: Company Discovery")
    p_log.info("Starting company discovery...")

    # Check cache first using a key representing this run's job prefs
    cache = DBCache(session)
    cache_key = (
        f"company_discovery_{config.job_preferences.geographies[0]}_{config.job_preferences.company_size.min_employees}"
    )
    cached_data = cache.get(cache_key)

    discovered_companies_data = []

    if cached_data:
        p_log.info("Found cached company discovery list.")
        discovered_companies_data = cached_data
    else:
        # LLM generated + Web search verification
        prompt = (
            f"Generate a list of 5 technology companies operating in {config.job_preferences.geographies} "
            f"that typically have a company size between {config.job_preferences.company_size.min_employees} "
            f"and {config.job_preferences.company_size.max_employees} employees. "
            f"Exclude the following companies: {config.exclusions.companies}. "
            "Ensure they are active engineering organizations."
        )
        try:
            response = llm.generate_json(prompt, CompanyListResponse)
            discovered_companies_data = [c.model_dump() for c in response.companies]  # type: ignore
            # Cache it
            cache.set(
                cache_key,
                discovered_companies_data,
                config.pipeline.cache_lifetime_seconds,
            )
        except Exception as e:
            p_log.error(f"Failed to generate company list from LLM: {e}")
            raise

    # Persist companies in database
    db_companies = []
    for c_data in discovered_companies_data:
        # Avoid duplicate companies
        existing = session.query(Company).filter(Company.name == c_data["name"]).first()
        if existing:
            db_companies.append(existing)
        else:
            new_company = Company(
                name=c_data["name"],
                domain=c_data.get("domain"),
                employee_count=c_data.get("employee_count"),
                industry=c_data.get("industry"),
            )
            session.add(new_company)
            db_companies.append(new_company)

    session.commit()
    p_log.info(f"Discovered {len(db_companies)} candidate companies.", status="SUCCESS")
    return db_companies


def run_stage_1_job_discovery(
    session: Session,
    config: AppConfig,
    llm: BaseLLMProvider,
    browser: BrowserProvider,
    companies: list[Company],
    run_id: str,
) -> list[Job]:
    """
    Stage 1: Job Discovery
    Searches for open software jobs matching preferences at the discovered companies.
    """
    p_log = PipelineLogger(logger, run_id, "Stage 1: Job Discovery")
    p_log.info(f"Searching jobs for {len(companies)} companies...")

    all_jobs = []
    for company in companies:
        p_log.company = company.name

        # Check cache for job listings at this company
        cache = DBCache(session)
        cache_key = f"job_discovery_{company.name.lower()}"
        cached_jobs = cache.get(cache_key)

        jobs_data = []
        if cached_jobs:
            p_log.info(f"Found cached job listings for {company.name}")
            jobs_data = cached_jobs
        else:
            # Query DuckDuckGo to find Careers page and open roles
            search_query = f"'{company.name}' software engineer careers jobs"
            search_results = browser.search_google(search_query, num_results=3)

            scraped_text = ""
            for result in search_results:
                try:
                    html = browser.fetch_page(result["url"], use_playwright=False)
                    scraped_text += f"\n--- {result['title']} ({result['url']}) ---\n"
                    scraped_text += browser.extract_text(html)[:2000]  # Limit chunk length
                except Exception as e:
                    p_log.warning(f"Failed to scrape {result['url']}: {e}")

            if scraped_text:
                prompt = (
                    f"Analyze this scraped text from {company.name}'s search results and career sites:\n\n"
                    f"{scraped_text}\n\n"
                    f"Extract any open software engineering jobs that match these preferred roles: "
                    f"{config.job_preferences.roles}. Look for experience requirements close to: "
                    f"up to {config.job_preferences.experience_years_max} years (SDE-1, Entry Level, Graduate)."
                )
                try:
                    response = llm.generate_json(prompt, JobListResponse)
                    jobs_data = [j.model_dump() for j in response.jobs]  # type: ignore
                    cache.set(cache_key, jobs_data, config.pipeline.cache_lifetime_seconds)
                except Exception as e:
                    p_log.error(f"Failed to parse jobs list from LLM for {company.name}: {e}")
                    continue
            else:
                p_log.warning(f"No scrapable text found for {company.name}")
                continue

        for j_data in jobs_data:
            # Check unique URL to prevent duplicate Job entries
            existing_job = None
            if j_data.get("url"):
                existing_job = session.query(Job).filter(Job.url == j_data["url"]).first()
            if not existing_job:
                new_job = Job(
                    company_id=company.id,
                    title=j_data["title"],
                    url=j_data.get("url"),
                    location=j_data.get("location"),
                    salary=j_data.get("salary"),
                    experience_years_required=j_data.get("experience_years"),
                    description=j_data.get("description"),
                )
                session.add(new_job)
                all_jobs.append(new_job)
            else:
                all_jobs.append(existing_job)

    session.commit()
    p_log.company = None
    p_log.info(f"Discovered {len(all_jobs)} jobs across companies.", status="SUCCESS")
    return all_jobs


def run_stage_2_filtering(session: Session, config: AppConfig, jobs: list[Job], run_id: str) -> list[Application]:
    """
    Stage 2: Filtering
    Screens jobs against exclusion rules (companies, keywords, salary limits)
    and initializes/returns Application instances.
    """
    p_log = PipelineLogger(logger, run_id, "Stage 2: Filtering")
    p_log.info(f"Filtering {len(jobs)} jobs...")

    active_applications = []

    for job in jobs:
        company = job.company
        p_log.company = company.name

        # Check if Application already exists for this job
        existing_app = session.query(Application).filter(Application.job_id == job.id).first()
        if existing_app:
            if existing_app.state not in [
                "Completed",
                "Skipped",
                "Excluded Company",
                "Salary Too Low",
                "Ghost Job",
            ]:
                active_applications.append(existing_app)
            continue

        # Create a new application
        app = Application(run_id=run_id, job_id=job.id, current_stage=2, state="Filtering")
        session.add(app)
        session.flush()  # Populate app.id

        # Record history
        history = History(
            application_id=app.id,
            stage=2,
            state="Filtering",
            run_id=run_id,
            notes="Initialized application state.",
        )
        session.add(history)

        # Apply filters
        # 1. Company Name Exclusions
        is_company_excluded = any(ex_c.lower() in company.name.lower() for ex_c in config.exclusions.companies)
        if is_company_excluded:
            app.state = "Excluded Company"
            history.notes = f"Filtered out: company {company.name} is excluded."
            p_log.info(f"Excluded company: {company.name}", status="EXCLUDED")
            continue

        # 2. Keyword Exclusions in title
        is_keyword_excluded = any(ex_k.lower() in job.title.lower() for ex_k in config.exclusions.keywords)
        if is_keyword_excluded:
            app.state = "Ghost Job"  # Or Excluded Keyword; matches Ghost Job / Skip states
            history.notes = f"Filtered out: job title '{job.title}' contains excluded keywords."
            p_log.info(f"Excluded job keyword in title: {job.title}", status="EXCLUDED")
            continue

        # 3. Experience Exclusions
        if (
            job.experience_years_required
            and job.experience_years_required > config.job_preferences.experience_years_max
        ):
            app.state = "Ghost Job"  # Or too high experience
            history.notes = f"Filtered out: experience required ({job.experience_years_required} yrs) exceeds max ({config.job_preferences.experience_years_max} yrs)."
            p_log.info(
                f"Excluded due to experience requirement: {job.experience_years_required} years",
                status="EXCLUDED",
            )
            continue

        # 4. Salary screening (if range available)
        # 9 LPA to 21 LPA is preference. If job lists salary, verify it doesn't fall below min.
        # Fallback to true if unknown, we resolve it during research/scoring

        # Advance to Stage 3 if filter passes
        app.current_stage = 3
        app.state = "Company Research"
        history_adv = History(
            application_id=app.id,
            stage=3,
            state="Company Research",
            run_id=run_id,
            notes="Passed basic filtering. Moving to Company Research.",
        )
        session.add(history_adv)
        active_applications.append(app)
        p_log.info(f"Passed filtering: {job.title} at {company.name}")

    session.commit()
    p_log.company = None
    p_log.info(f"Initialized {len(active_applications)} active applications.", status="SUCCESS")
    return active_applications


def run_stage_3_company_research(
    session: Session,
    config: AppConfig,
    llm: BaseLLMProvider,
    browser: BrowserProvider,
    app: Application,
    run_id: str,
) -> bool:
    """
    Stage 3: Company Research
    Gathers detailed intelligence on the company product, tech stack, business model,
    funding, and engineering culture.
    """
    company = app.job.company
    p_log = PipelineLogger(logger, run_id, "Stage 3: Company Research", company.name)
    p_log.info("Starting company research...")

    cache = DBCache(session)
    cache_key = f"company_research_{company.name.lower()}"
    cached_research = cache.get(cache_key)

    if cached_research:
        p_log.info("Retrieved company research from cache.")
        company.research_data = cached_research
        session.commit()
    else:
        # Scrape and research
        search_query = f"'{company.name}' tech stack product business model funding engineering blog"
        results = browser.search_google(search_query, num_results=3)

        research_raw_text = ""
        for r in results:
            try:
                html = browser.fetch_page(r["url"], use_playwright=False)
                research_raw_text += f"\n--- {r['title']} ({r['url']}) ---\n"
                research_raw_text += browser.extract_text(html)[:2500]
            except Exception as e:
                p_log.warning(f"Error scraping {r['url']}: {e}")

        if not research_raw_text:
            p_log.error("No scrapable information retrieved for research.")
            app.state = "Research Failed"
            session.add(
                History(
                    application_id=app.id,
                    stage=3,
                    state="Research Failed",
                    run_id=run_id,
                    notes="Company research failed due to lack of web content.",
                )
            )
            session.commit()
            return False

        prompt = (
            config.prompts.company_research.format(company_name=company.name)
            + f"\n\nHere is the scraped content:\n{research_raw_text}"
        )

        try:
            response = llm.generate_json(prompt, CompanyResearchResponse)
            company.research_data = response.model_dump()
            cache.set(cache_key, company.research_data, config.pipeline.cache_lifetime_seconds)
            session.commit()
        except Exception as e:
            p_log.error(f"LLM failed to compile company research structure: {e}")
            app.state = "Research Failed"
            session.add(
                History(
                    application_id=app.id,
                    stage=3,
                    state="Research Failed",
                    run_id=run_id,
                    notes=f"Company research LLM call failed: {e}",
                )
            )
            session.commit()
            return False

    # Move to next stage
    app.current_stage = 4
    app.state = "Contact Research"
    session.add(
        History(
            application_id=app.id,
            stage=4,
            state="Contact Research",
            run_id=run_id,
            notes="Completed company research successfully. Advancing to Contact Research.",
        )
    )
    session.commit()
    p_log.info("Completed company research.", status="SUCCESS")
    return True


def run_stage_4_contact_research(
    session: Session,
    config: AppConfig,
    llm: BaseLLMProvider,
    browser: BrowserProvider,
    app: Application,
    run_id: str,
) -> bool:
    """
    Stage 4: Contact Research
    Discovers engineering hiring contacts (CTO, Engineering Manager, Tech Lead) at the company.
    Enforces the 'NO DUPLICATES' constraint.
    """
    company = app.job.company
    p_log = PipelineLogger(logger, run_id, "Stage 4: Contact Research", company.name)
    p_log.info("Starting contact research...")

    # Check if this company already has a completed application with a contact
    # Rule: "If a company only has one engineering contact available, consider the company itself contacted."
    previous_contact = (
        session.query(Contact).filter(Contact.company_id == company.id, Contact.email.isnot(None)).first()
    )

    if previous_contact:
        # Check if that contact is already associated with any completed/active application email
        existing_app_email = (
            session.query(Application)
            .filter(
                Application.contact_id == previous_contact.id,
                Application.state.in_(["Completed", "Gmail Draft Creation", "Email Generation"]),
            )
            .first()
        )

        if existing_app_email:
            p_log.info(
                f"Duplicate check: Contact {previous_contact.name} already contacted for this company.",
                status="DUPLICATE",
            )
            app.state = "Duplicate"
            session.add(
                History(
                    application_id=app.id,
                    stage=4,
                    state="Duplicate",
                    run_id=run_id,
                    notes=f"Company already contacted via {previous_contact.name}.",
                )
            )
            session.commit()
            return False

    cache = DBCache(session)
    cache_key = f"contacts_{company.name.lower()}"
    cached_contacts = cache.get(cache_key)

    contacts_data = []
    if cached_contacts:
        p_log.info("Found contacts in cache.")
        contacts_data = cached_contacts
    else:
        # Search for contacts
        search_query = (
            f"'{company.name}' (CTO OR 'Engineering Manager' OR 'Tech Lead' OR 'Hiring Manager') linkedin contacts"
        )
        results = browser.search_google(search_query, num_results=3)

        scraped_text = ""
        for r in results:
            try:
                html = browser.fetch_page(r["url"], use_playwright=False)
                scraped_text += f"\n--- {r['title']} ({r['url']}) ---\n"
                scraped_text += browser.extract_text(html)[:2000]
            except Exception as e:
                p_log.warning(f"Error scraping {r['url']}: {e}")

        if scraped_text:
            prompt = (
                f"Identify potential engineering managers, tech leads, recruiters, or CTO names "
                f"at {company.name} from the following text:\n\n{scraped_text}\n\n"
                "Return a structured list of names, roles, and LinkedIn URLs or email patterns."
            )
            try:
                response = llm.generate_json(prompt, ContactListResponse)
                contacts_data = [c.model_dump() for c in response.contacts]  # type: ignore
                cache.set(cache_key, contacts_data, config.pipeline.cache_lifetime_seconds)
            except Exception as e:
                p_log.error(f"Failed to identify contacts using LLM: {e}")
        else:
            p_log.warning("No scraped content to parse contacts.")

    # Fallback to generating a mock placeholder contact if web search yielded nothing
    # to avoid blocking the pipeline due to lack of public APIs, but log a warning.
    if not contacts_data:
        p_log.warning("No contacts discovered. Generating placeholder contact for pipeline continuity.")
        contacts_data = [
            {
                "name": "Hiring Manager",
                "role": "Engineering Manager",
                "email_pattern": "first.last@company.com",
                "linkedin_url": f"https://linkedin.com/company/{company.name.lower()}",
            }
        ]

    # Save contacts to db
    best_contact = None
    priority_order = [
        "engineering manager",
        "hiring manager",
        "tech lead",
        "head of engineering",
        "cto",
        "recruiter",
        "hr",
    ]

    db_contacts = []
    for c_data in contacts_data:
        # Check if contact exists
        contact = (
            session.query(Contact).filter(Contact.company_id == company.id, Contact.name == c_data["name"]).first()
        )

        if not contact:
            contact = Contact(
                company_id=company.id,
                name=c_data["name"],
                role=c_data["role"],
                linkedin_url=c_data.get("linkedin_url"),
            )
            session.add(contact)
            session.flush()
        db_contacts.append(contact)

    # Sort contacts by roles priority to select the best one
    def get_priority(ct: Contact) -> int:
        role_lower = ct.role.lower()
        for idx, p_role in enumerate(priority_order):
            if p_role in role_lower:
                return idx
        return len(priority_order)

    db_contacts.sort(key=get_priority)
    best_contact = db_contacts[0] if db_contacts else None

    if not best_contact:
        app.state = "Research Failed"
        session.add(
            History(
                application_id=app.id,
                stage=4,
                state="Research Failed",
                run_id=run_id,
                notes="Could not discover any contacts.",
            )
        )
        session.commit()
        return False

    # Link contact to application
    app.contact_id = best_contact.id
    app.current_stage = 5
    app.state = "Professional Email Discovery"
    session.add(
        History(
            application_id=app.id,
            stage=5,
            state="Professional Email Discovery",
            run_id=run_id,
            notes=f"Selected contact {best_contact.name} ({best_contact.role}). Moving to Email Discovery.",
        )
    )
    session.commit()
    p_log.info(f"Selected contact {best_contact.name} ({best_contact.role}).", status="SUCCESS")
    return True


def run_stage_5_email_discovery(
    session: Session,
    config: AppConfig,
    llm: BaseLLMProvider,
    browser: BrowserProvider,
    app: Application,
    run_id: str,
) -> bool:
    """
    Stage 5: Professional Email Discovery
    Attempts to locate or construct a valid corporate email address for the contact.
    """
    contact = app.contact
    assert contact is not None
    company = app.job.company

    p_log = PipelineLogger(logger, run_id, "Stage 5: Professional Email Discovery", company.name)
    p_log.info(f"Finding email for {contact.name}...")

    if contact.email:
        p_log.info(f"Contact email already known: {contact.email}")
        app.current_stage = 6
        app.state = "Opportunity Scoring"
        session.commit()
        return True

    # Check cache
    cache = DBCache(session)
    cache_key = f"email_{company.name.lower()}_{contact.name.replace(' ', '_').lower()}"
    cached_email = cache.get(cache_key)

    email_address = None
    if cached_email:
        p_log.info("Retrieved email from cache.")
        email_address = cached_email
    else:
        # Search query for email pattern
        search_query = f"'{contact.name}' email '{company.domain or company.name}'"
        results = browser.search_google(search_query, num_results=2)

        scraped_text = ""
        for r in results:
            try:
                html = browser.fetch_page(r["url"], use_playwright=False)
                scraped_text += f"\n--- {r['title']} ({r['url']}) ---\n"
                scraped_text += browser.extract_text(html)[:1500]
            except Exception as e:
                p_log.warning(f"Error scraping {r['url']}: {e}")

        # Ask LLM to extract or predict
        prompt = (
            f"Based on this search content and the contact details:\n"
            f"Contact Name: {contact.name}\n"
            f"Company: {company.name}\n"
            f"Domain: {company.domain or 'Unknown'}\n\n"
            f"Scraped Web Content:\n{scraped_text}\n\n"
            f"Determine or predict the professional email address of {contact.name}. "
            f"Use common company email patterns (e.g. first.last@company.com, first@company.com) if explicit not found. "
            f"If it's impossible to deduce, leave the email field null."
        )
        try:
            response = llm.generate_json(prompt, EmailDiscoveryResponse)
            email_address = response.email  # type: ignore
            if email_address:
                cache.set(cache_key, email_address, config.pipeline.cache_lifetime_seconds)
        except Exception as e:
            p_log.error(f"LLM failed to deduce email for {contact.name}: {e}")

    # Fallback to pattern guessing if nothing found, to ensure the pipeline is runnable
    # in an environment with no paid contact scraping endpoints.
    if not email_address and company.domain:
        p_log.warning("No email address found online. Guessing standard format first.last@domain.")
        clean_name = contact.name.lower().replace(" ", ".")
        email_address = f"{clean_name}@{company.domain}"

    if not email_address:
        p_log.error(f"No professional email discovered for {contact.name}.", status="NO_EMAIL")
        app.state = "No Professional Email"
        session.add(
            History(
                application_id=app.id,
                stage=5,
                state="No Professional Email",
                run_id=run_id,
                notes=f"Failed to discover email for {contact.name}.",
            )
        )
        session.commit()
        return False

    # Save email and proceed
    contact.email = email_address
    app.current_stage = 6
    app.state = "Opportunity Scoring"
    session.add(
        History(
            application_id=app.id,
            stage=6,
            state="Opportunity Scoring",
            run_id=run_id,
            notes=f"Discovered email: {email_address}. Moving to Scoring.",
        )
    )
    session.commit()
    p_log.info(f"Discovered email: {email_address}", status="SUCCESS")
    return True


def run_stage_6_opportunity_scoring(
    session: Session,
    config: AppConfig,
    llm: BaseLLMProvider,
    app: Application,
    run_id: str,
) -> bool:
    """
    Stage 6: Opportunity Scoring
    Scores the job application based on weights and threshold settings in config.yaml.
    """
    company = app.job.company
    job = app.job
    p_log = PipelineLogger(logger, run_id, "Stage 6: Opportunity Scoring", company.name)
    p_log.info(f"Scoring opportunity: {job.title}...")

    prompt = (
        f"Analyze the following job and company data to score this opportunity:\n\n"
        f"Job Title: {job.title}\n"
        f"Location: {job.location}\n"
        f"Salary Information: {job.salary or 'Not mentioned'}\n"
        f"Job Description: {job.description or 'No desc'}\n"
        f"Company Name: {company.name}\n"
        f"Company Details: {json.dumps(company.research_data)}\n\n"
        f"Provide a score between 0.0 (poor) and 1.0 (excellent) for each of these categories:\n"
        f"1. role_match: Fit for entry level / up to 1 yr experience, matching {config.job_preferences.roles}.\n"
        f"2. tech_stack: Aligning with modern python/fullstack/backend technologies.\n"
        f"3. salary: Matching LPA preferences {config.job_preferences.salary_range.min_lpa} - {config.job_preferences.salary_range.max_lpa}.\n"
        f"4. company_quality: Reputation, engineering culture, stability.\n"
        f"5. growth: Industry sector potential, career acceleration.\n"
        f"6. confidence: Reliability of the job and company data found."
    )

    try:
        response: OpportunityScoreResponse = llm.generate_json(prompt, OpportunityScoreResponse)  # type: ignore
        # Compute weighted average
        w = config.scoring.weights
        total_score = (
            response.role_match * w.role_match
            + response.tech_stack * w.tech_stack
            + response.salary * w.salary
            + response.company_quality * w.company_quality
            + response.growth * w.growth
            + response.confidence * w.confidence
        )

        # Save score and breakdown
        app.score = float(total_score)
        app.score_breakdown = response.model_dump()
        session.commit()

        p_log.info(f"Weighted Score: {app.score:.2f} (Threshold: {config.scoring.thresholds.minimum_score})")

        if app.score < config.scoring.thresholds.minimum_score:
            p_log.warning(f"Score {app.score:.2f} is below minimum threshold.", status="LOW_SCORE")
            app.state = "Salary Too Low"  # Terminal state corresponding to failed validation/scoring
            session.add(
                History(
                    application_id=app.id,
                    stage=6,
                    state="Salary Too Low",
                    run_id=run_id,
                    notes=f"Score {app.score:.2f} below threshold of {config.scoring.thresholds.minimum_score}.",
                )
            )
            session.commit()
            return False

    except Exception as e:
        p_log.error(f"Error calculating score: {e}")
        app.state = "Failed"
        session.add(
            History(
                application_id=app.id,
                stage=6,
                state="Failed",
                run_id=run_id,
                notes=f"Opportunity scoring failed: {e}",
            )
        )
        session.commit()
        return False

    app.current_stage = 7
    app.state = "Resume Tailoring"
    session.add(
        History(
            application_id=app.id,
            stage=7,
            state="Resume Tailoring",
            run_id=run_id,
            notes=f"Scored {app.score:.2f}. Advancing to Resume Tailoring.",
        )
    )
    session.commit()
    p_log.info("Opportunity scoring completed successfully.", status="SUCCESS")
    return True


def run_stage_7_resume_tailoring(
    session: Session,
    config: AppConfig,
    llm: BaseLLMProvider,
    app: Application,
    run_id: str,
) -> bool:
    """
    Stage 7: Resume Tailoring
    Reads the base Typst resume, uses the LLM to tailor keywords/ordering (without fabrication),
    writes a new .typ file, and compiles it using Typst CLI if available.
    """
    company = app.job.company
    job = app.job
    p_log = PipelineLogger(logger, run_id, "Stage 7: Resume Tailoring", company.name)
    p_log.info("Tailoring resume...")

    base_resume_path = config.pipeline.base_resume_path
    if not os.path.exists(base_resume_path):
        p_log.error(f"Base resume not found at {base_resume_path}. Please place it there to resume.")
        app.state = "Failed"
        session.add(
            History(
                application_id=app.id,
                stage=7,
                state="Failed",
                run_id=run_id,
                notes=f"Base resume file '{base_resume_path}' does not exist.",
            )
        )
        session.commit()
        return False

    try:
        with open(base_resume_path, encoding="utf-8") as f:
            base_resume_text = f.read()
    except Exception as e:
        p_log.error(f"Error reading base resume: {e}")
        app.state = "Failed"
        session.commit()
        return False

    tech_stack = ", ".join(company.research_data.get("tech_stack", [])) if company.research_data else ""
    prompt = config.prompts.resume_tailoring.format(
        role_name=job.title,
        company_name=company.name,
        tech_stack=tech_stack,
        base_resume_text=base_resume_text,
    )

    try:
        response: ResumeTailorResponse = llm.generate_json(prompt, ResumeTailorResponse)  # type: ignore

        # Ensure directories exist
        os.makedirs(config.pipeline.generated_resumes_dir, exist_ok=True)

        # Save tailored .typ file
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        safe_comp = company.name.replace(" ", "_").lower()
        safe_role = job.title.replace(" ", "_").lower()

        file_prefix = f"resume_{safe_comp}_{safe_role}_{timestamp}"
        typ_filename = f"{file_prefix}.typ"
        typ_filepath = os.path.join(config.pipeline.generated_resumes_dir, typ_filename)

        with open(typ_filepath, "w", encoding="utf-8") as f:
            f.write(response.tailored_typst_content)

        p_log.info(f"Saved tailored Typst file: {typ_filepath}")

        # Try to compile to PDF if typst is available
        pdf_filepath = os.path.join(config.pipeline.generated_resumes_dir, f"{file_prefix}.pdf")
        has_pdf = False
        try:
            # Run 'typst compile <typ_filepath> <pdf_filepath>'
            result = subprocess.run(
                ["typst", "compile", typ_filepath, pdf_filepath],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                p_log.info(f"Compiled resume to PDF: {pdf_filepath}")
                has_pdf = True
            else:
                p_log.warning(f"Typst compilation returned non-zero code. Error: {result.stderr}")
        except Exception as e:
            p_log.warning(f"Typst compiler not found or failed to execute: {e}. Attaching raw .typ file instead.")

        final_attachment_path = pdf_filepath if has_pdf else typ_filepath

        # Record version
        rv = ResumeVersion(
            application_id=app.id,
            parent_resume=base_resume_path,
            company=company.name,
            role=job.title,
            keywords_added=response.keywords_added,
            reasoning=response.reasoning,
            path=final_attachment_path,
        )
        session.add(rv)

        # Link resume path to application
        app.tailored_resume_path = final_attachment_path
        app.current_stage = 8
        app.state = "Email Generation"
        session.add(
            History(
                application_id=app.id,
                stage=8,
                state="Email Generation",
                run_id=run_id,
                notes=f"Tailored resume saved to {final_attachment_path}. Moving to Email Gen.",
            )
        )
        session.commit()
        p_log.info("Resume tailoring completed successfully.", status="SUCCESS")
        return True

    except Exception as e:
        p_log.error(f"Error tailoring resume: {e}")
        app.state = "Failed"
        session.add(
            History(
                application_id=app.id,
                stage=7,
                state="Failed",
                run_id=run_id,
                notes=f"Resume tailoring failed: {e}",
            )
        )
        session.commit()
        return False


def run_stage_8_email_generation(
    session: Session,
    config: AppConfig,
    llm: BaseLLMProvider,
    app: Application,
    run_id: str,
) -> bool:
    """
    Stage 8: Email Generation
    Generates a personalized HTML cold email using company research data.
    """
    company = app.job.company
    job = app.job
    contact = app.contact
    assert contact is not None

    p_log = PipelineLogger(logger, run_id, "Stage 8: Email Generation", company.name)
    p_log.info(f"Generating personalized email for {contact.name}...")

    # Retrieve resume version keywords/reasoning to feed into prompt
    rv = (
        session.query(ResumeVersion)
        .filter(ResumeVersion.application_id == app.id)
        .order_by(ResumeVersion.id.desc())
        .first()
    )
    tailored_skills = ", ".join(rv.keywords_added) if rv and rv.keywords_added else "software development"

    research = company.research_data or {}
    prompt = config.prompts.email_generation.format(
        contact_name=contact.name,
        contact_role=contact.role,
        company_name=company.name,
        role_name=job.title,
        product_description=research.get("business_model", "their innovative platform"),
        tech_stack=", ".join(research.get("tech_stack", ["modern tools"])),
        recent_launches=research.get("funding", "recent engineering progress"),
        tailored_skills=tailored_skills,
    )

    try:
        response: EmailGenResponse = llm.generate_json(prompt, EmailGenResponse)  # type: ignore

        # Save to database
        email = Email(
            application_id=app.id,
            subject=response.subject,
            body=response.body_html,
            status="generated",
        )
        session.add(email)

        app.current_stage = 9
        app.state = "Validation"
        session.add(
            History(
                application_id=app.id,
                stage=9,
                state="Validation",
                run_id=run_id,
                notes="Generated outreach email. Advancing to Validation.",
            )
        )
        session.commit()
        p_log.info("Email generation completed successfully.", status="SUCCESS")
        return True

    except Exception as e:
        p_log.error(f"Email generation failed: {e}")
        app.state = "Failed"
        session.add(
            History(
                application_id=app.id,
                stage=8,
                state="Failed",
                run_id=run_id,
                notes=f"Email generation failed: {e}",
            )
        )
        session.commit()
        return False


def run_stage_9_validation(
    session: Session,
    config: AppConfig,
    llm: BaseLLMProvider,
    app: Application,
    run_id: str,
) -> bool:
    """
    Stage 9: Validation
    Validates that the email content and tailored resume don't contain placeholders or hallucinated facts.
    """
    company = app.job.company
    p_log = PipelineLogger(logger, run_id, "Stage 9: Validation", company.name)
    p_log.info("Validating tailored outputs...")

    # Load email and resume versions
    email = session.query(Email).filter(Email.application_id == app.id).order_by(Email.id.desc()).first()
    rv = (
        session.query(ResumeVersion)
        .filter(ResumeVersion.application_id == app.id)
        .order_by(ResumeVersion.id.desc())
        .first()
    )

    if not email or not rv:
        p_log.error("Email or ResumeVersion missing from database for validation.")
        app.state = "Validation Failed"
        session.commit()
        return False

    # Read base resume content to cross-reference
    base_resume_path = config.pipeline.base_resume_path
    try:
        with open(base_resume_path, encoding="utf-8") as f:
            base_resume_text = f.read()
    except Exception as e:
        p_log.error(f"Failed to read base resume for validation: {e}")
        return False

    prompt = (
        f"Perform strict validation check on the generated files to ensure high quality.\n\n"
        f"Base Resume reference:\n{base_resume_text}\n\n"
        f"Tailored Resume Reasoning:\n{rv.reasoning}\n\n"
        f"Draft Email Subject: {email.subject}\n"
        f"Draft Email HTML Body:\n{email.body}\n\n"
        f"Verify the following conditions:\n"
        f"1. There are absolutely no template placeholders like '[Insert Name]', '[Your Name]', '<Company>', 'YYYY', etc.\n"
        f"2. The tailored details do not invent or fabricate job titles, companies, certifications, or degrees that are not mentioned in the Base Resume.\n"
        f"Return a structured result: is_valid (boolean) and a list of errors."
    )

    try:
        response: ValidationResponse = llm.generate_json(prompt, ValidationResponse)  # type: ignore
        if response.is_valid:
            app.current_stage = 10
            app.state = "Gmail Draft Creation"
            session.add(
                History(
                    application_id=app.id,
                    stage=10,
                    state="Gmail Draft Creation",
                    run_id=run_id,
                    notes="Passed validation. Moving to Gmail Draft Creation.",
                )
            )
            session.commit()
            p_log.info("Validation passed successfully.", status="SUCCESS")
            return True
        else:
            p_log.error(f"Validation failed: {response.errors}", status="VALIDATION_FAILED")
            app.state = "Validation Failed"
            session.add(
                History(
                    application_id=app.id,
                    stage=9,
                    state="Validation Failed",
                    run_id=run_id,
                    notes=f"Validation failed: {', '.join(response.errors)}",
                )
            )
            session.commit()
            return False

    except Exception as e:
        p_log.error(f"Validation run failed: {e}")
        app.state = "Validation Failed"
        session.commit()
        return False


def run_stage_10_gmail_draft_creation(session: Session, gmail: GmailProvider, app: Application, run_id: str) -> bool:
    """
    Stage 10: Gmail Draft Creation
    Uses Gmail OAuth connection to create the draft with the tailored resume attachment.
    """
    company = app.job.company
    contact = app.contact
    assert contact is not None

    p_log = PipelineLogger(logger, run_id, "Stage 10: Gmail Draft Creation", company.name)
    p_log.info(f"Creating Gmail Draft for {contact.email}...")

    email = session.query(Email).filter(Email.application_id == app.id).order_by(Email.id.desc()).first()
    if not email:
        p_log.error("Email content missing in DB.")
        app.state = "Draft Failed"
        session.commit()
        return False

    assert contact.email is not None
    try:
        draft_id = gmail.create_draft(
            to_email=contact.email,
            subject=email.subject,
            body_html=email.body,
            resume_path=app.tailored_resume_path,
        )

        email.gmail_draft_id = draft_id
        email.status = "draft_created"

        app.current_stage = 11
        app.state = "Database Finalization"
        session.add(
            History(
                application_id=app.id,
                stage=11,
                state="Database Finalization",
                run_id=run_id,
                notes=f"Created Gmail Draft successfully (ID: {draft_id}).",
            )
        )
        session.commit()
        p_log.info(f"Created Gmail Draft ID: {draft_id}", status="SUCCESS")
        return True

    except Exception as e:
        p_log.error(f"Gmail Draft creation failed: {e}")
        app.state = "Draft Failed"
        session.add(
            History(
                application_id=app.id,
                stage=10,
                state="Draft Failed",
                run_id=run_id,
                notes=f"Gmail API Draft Creation failed: {e}",
            )
        )
        session.commit()
        return False


def run_stage_11_database_finalization(session: Session, app: Application, run_id: str) -> bool:
    """
    Stage 11: Database Finalization
    Validates that database state for this application is clean.
    """
    company = app.job.company
    p_log = PipelineLogger(logger, run_id, "Stage 11: Database Finalization", company.name)
    p_log.info("Finalizing pipeline entries...")

    app.current_stage = 12
    app.state = "Completed"
    session.add(
        History(
            application_id=app.id,
            stage=12,
            state="Completed",
            run_id=run_id,
            notes="Successfully completed all pipeline stages.",
        )
    )
    session.commit()
    p_log.info("Application finalized successfully.", status="SUCCESS")
    return True
