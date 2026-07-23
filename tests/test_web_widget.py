from sqlalchemy import create_engine

from src.db.models import Application, Base, Company, Contact, Email, History, Job, ResumeVersion, Run
from src.db.session import get_session_factory
from src.web_server import (
    STAGE_NAMES,
    get_all_applications,
    get_application_details,
    get_companies,
    get_contacts,
    get_db_status,
    get_jobs,
)


def test_stage_names_mapping():
    assert STAGE_NAMES[0] == "Company Discovery"
    assert STAGE_NAMES[12] == "Completed"
    assert len(STAGE_NAMES) == 13


def test_get_db_status_nonexistent_file():
    res = get_db_status("nonexistent_path.db")
    assert "error" in res
    assert res["active_jobs_count"] == 0


def test_get_db_status_valid_db(tmp_path):
    db_file = str(tmp_path / "test_platform.db")
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    session_factory = get_session_factory(db_file)
    session = session_factory()

    comp = Company(id=1, name="Acme Corp")
    job = Job(id=10, company_id=1, title="Senior Engineer")
    run = Run(id="RUN-1", status="running")
    app = Application(id=100, run_id="RUN-1", job_id=10, current_stage=3, state="Company Research", score=8.5)

    session.add_all([comp, job, run, app])
    session.commit()
    session.close()

    res = get_db_status(db_file)
    assert res["active_jobs_count"] == 1
    assert res["active_runs_count"] == 1
    assert len(res["jobs"]) == 1

    job_res = res["jobs"][0]
    assert job_res["company_name"] == "Acme Corp"
    assert job_res["job_title"] == "Senior Engineer"
    assert job_res["current_stage"] == 3
    assert job_res["stage_name"] == "Company Research"
    assert job_res["stage_percent"] == 25


def test_web_server_extended_api_helpers(tmp_path):
    db_file = str(tmp_path / "test_extended.db")
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    session_factory = get_session_factory(db_file)
    session = session_factory()

    comp = Company(id=1, name="TechCorp", domain="techcorp.com", industry="AI", employee_count=150)
    job = Job(id=10, company_id=1, title="AI Architect", location="Remote", salary="₹30L")
    ct = Contact(id=5, company_id=1, name="Alice Smith", role="VP Eng", email="alice@techcorp.com")
    run = Run(id="RUN-99", status="completed")
    app = Application(
        id=101,
        run_id="RUN-99",
        job_id=10,
        contact_id=5,
        current_stage=10,
        state="Gmail Draft Creation",
        score=9.2,
        score_breakdown={"role_match": 1.0, "salary_match": 0.9},
        tailored_resume_path="resumes/generated/techcorp_resume.pdf",
    )
    email = Email(
        id=1,
        application_id=101,
        subject="AI Architect Role",
        body="<p>Hi Alice</p>",
        gmail_draft_id="r12345",
        status="draft_created",
    )
    res_ver = ResumeVersion(
        id=1,
        application_id=101,
        parent_resume="base.typ",
        company="TechCorp",
        role="AI Architect",
        keywords_added=["PyTorch", "LLM"],
        reasoning="Matched AI focus",
        path="resumes/generated/techcorp_resume.pdf",
    )
    hist = History(id=1, application_id=101, stage=10, state="Gmail Draft Creation", run_id="RUN-99", notes="Draft created")

    session.add_all([comp, job, ct, run, app, email, res_ver, hist])
    session.commit()
    session.close()

    # Test get_all_applications
    apps_list = get_all_applications(db_file)
    assert len(apps_list) == 1
    assert apps_list[0]["id"] == 101
    assert apps_list[0]["company_name"] == "TechCorp"
    assert apps_list[0]["contact_email"] == "alice@techcorp.com"

    # Test get_application_details
    details = get_application_details(db_file, 101)
    assert details is not None
    assert details["company"]["name"] == "TechCorp"
    assert details["job"]["title"] == "AI Architect"
    assert details["contact"]["name"] == "Alice Smith"
    assert details["email"]["gmail_draft_id"] == "r12345"
    assert details["resume"]["keywords_added"] == ["PyTorch", "LLM"]
    assert len(details["history"]) == 1

    # Test get_companies
    comps = get_companies(db_file)
    assert len(comps) == 1
    assert comps[0]["name"] == "TechCorp"

    # Test get_contacts
    contacts = get_contacts(db_file)
    assert len(contacts) == 1
    assert contacts[0]["email"] == "alice@techcorp.com"

    # Test get_jobs
    jobs = get_jobs(db_file)
    assert len(jobs) == 1
    assert jobs[0]["title"] == "AI Architect"


def test_ensure_widget_server_running_when_already_active():
    from unittest.mock import patch

    from src.web_server import ensure_widget_server_running

    with patch("src.web_server.is_widget_server_running", return_value=True), \
         patch("webbrowser.open") as mock_open:
        res = ensure_widget_server_running(auto_open=True)
        assert res is True
        mock_open.assert_not_called()

