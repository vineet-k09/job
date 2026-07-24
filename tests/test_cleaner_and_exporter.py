from sqlalchemy import create_engine

from src.db.models import Application, Base, Company, Contact, Email, Job, Run
from src.db.session import get_session_factory
from src.utils.cleaner import clean_invalid_emails_and_states
from src.utils.exporter import export_outreach_data


def setup_test_db(tmp_path):
    db_file = str(tmp_path / "test_platform.db")
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    session_factory = get_session_factory(db_file)
    session = session_factory()

    run = Run(id="RUN-1", status="running")
    comp = Company(id=1, name="Acme Corp", domain="mocktech.com", industry="Tech", employee_count=100)
    job = Job(id=10, company_id=1, title="AI Engineer", location="Remote", salary="30 LPA")
    contact1 = Contact(id=100, company_id=1, name="John Doe", role="Tech Lead", email="invalid-email-no-mx-12345.xyz")
    contact2 = Contact(id=101, company_id=1, name="Jane Smith", role="CTO", email="jane@mocktech.com")

    app1 = Application(id=1, run_id="RUN-1", job_id=10, contact_id=100, current_stage=3, state="Professional Email Discovery", score=8.5)
    app2 = Application(id=2, run_id="RUN-1", job_id=10, contact_id=101, current_stage=10, state="Completed", score=9.2)
    email2 = Email(id=50, application_id=2, subject="Hi Jane", body="<p>Hello world</p>", gmail_draft_id="DRAFT-123")

    session.add_all([run, comp, job, contact1, contact2, app1, app2, email2])
    session.commit()
    session.close()
    return db_file


def test_cleaner_never_deletes_records(tmp_path):
    db_file = setup_test_db(tmp_path)
    clean_invalid_emails_and_states(db_file)

    session_factory = get_session_factory(db_file)
    session = session_factory()

    # Verify ZERO rows were deleted
    comp_count = session.query(Company).count()
    job_count = session.query(Job).count()
    contact_count = session.query(Contact).count()
    email_count = session.query(Email).count()

    assert comp_count == 1
    assert job_count == 1
    assert contact_count == 2
    assert email_count == 1

    # Verify invalid email cleared on contact 100
    c100 = session.query(Contact).filter(Contact.id == 100).first()
    c101 = session.query(Contact).filter(Contact.id == 101).first()
    assert c100.email is None
    assert c101.email == "jane@mocktech.com"

    session.close()


def test_incremental_exporter(tmp_path):
    db_file = setup_test_db(tmp_path)
    export_dir = str(tmp_path / "exports")

    # Run 1: Should export 2 records
    res1 = export_outreach_data(db_path=db_file, export_dir=export_dir)
    assert res1["exported_count"] == 2

    # Run 2: No new records, should return 0 incremental exports
    res2 = export_outreach_data(db_path=db_file, export_dir=export_dir)
    assert res2["exported_count"] == 0
    assert "Incremental export skipped" in res2["message"]
