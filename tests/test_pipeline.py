import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import load_config
from src.db.models import Application, Base, Email
from src.pipeline.runner import PipelineRunner
from src.pipeline.stages import (
    CompanyListResponse,
    CompanyResearchResponse,
    ContactListResponse,
    EmailDiscoveryResponse,
    EmailGenResponse,
    JobListResponse,
    OpportunityScoreResponse,
    ResumeTailorResponse,
    ValidationResponse,
)


# Mock classes
class MockLLMProvider:
    def __init__(self, *args, **kwargs):
        pass

    def generate_text(self, prompt: str, system_prompt: str = None) -> str:
        return "Mock response text"

    def generate_json(self, prompt: str, schema, system_prompt: str = None):
        # Dynamically return matching mock responses based on schema type
        if "CompanyListResponse" in str(schema):
            return CompanyListResponse(
                companies=[
                    {
                        "name": "MockTech",
                        "domain": "mocktech.com",
                        "employee_count": 150,
                        "industry": "SaaS",
                    }
                ]
            )
        elif "JobListResponse" in str(schema):
            return JobListResponse(
                jobs=[
                    {
                        "title": "Software Engineer",
                        "url": "http://mocktech.com/jobs/1",
                        "location": "Remote",
                        "salary": "12 LPA",
                        "experience_years": 0.5,
                        "description": "Python developer role.",
                    }
                ]
            )
        elif "CompanyResearchResponse" in str(schema):
            return CompanyResearchResponse(
                business_model="B2B SaaS product",
                funding="Series A 5M USD",
                tech_stack=["Python", "FastAPI", "React"],
                culture="Remote friendly, high ownership",
                leadership=["CTO Alice", "CEO Bob"],
            )
        elif "ContactListResponse" in str(schema):
            return ContactListResponse(
                contacts=[
                    {
                        "name": "Alice Developer",
                        "role": "Engineering Manager",
                        "email_pattern": "alice@mocktech.com",
                        "linkedin_url": "https://linkedin.com/alice",
                    }
                ]
            )
        elif "EmailDiscoveryResponse" in str(schema):
            return EmailDiscoveryResponse(
                email="alice@mocktech.com", pattern_used="explicit"
            )
        elif "OpportunityScoreResponse" in str(schema):
            return OpportunityScoreResponse(
                role_match=0.9,
                tech_stack=0.9,
                salary=0.8,
                company_quality=0.8,
                growth=0.8,
                confidence=0.9,
                reasoning="Excellent match.",
            )
        elif "ResumeTailorResponse" in str(schema):
            return ResumeTailorResponse(
                tailored_typst_content="= Tailored Resume Content",
                keywords_added=["FastAPI", "Playwright"],
                reasoning="Aligned experience.",
            )
        elif "EmailGenResponse" in str(schema):
            return EmailGenResponse(
                subject="Exciting role at MockTech",
                body_html="<p>Hi Alice, I love your product...</p>",
            )
        elif "ValidationResponse" in str(schema):
            return ValidationResponse(is_valid=True, errors=[])

        raise ValueError(f"No mock handler for schema {schema}")


class MockBrowserProvider:
    def search_google(self, query, num_results=5):
        return [
            {
                "title": "Mock Link",
                "url": "http://example.com/mock",
                "snippet": "Snippet content",
            }
        ]

    def fetch_page(self, url, use_playwright=False):
        return "<html><body>Mock Careers text</body></html>"

    def extract_text(self, html):
        return "Mock Careers text"


class MockGmailProvider:
    def __init__(self, *args, **kwargs):
        pass

    def authenticate(self, interactive=True):
        return True

    def create_draft(self, to_email, subject, body_html, resume_path=None):
        return "draft_abc123"


def test_pipeline_integration(tmp_path):
    """
    Test the full pipeline stages workflow end-to-end
    using mocked LLM, Browser, and Gmail APIs over an in-memory SQLite DB.
    """
    # 1. Setup in-memory SQLite DB
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # 2. Setup mock runner config
    config_data = load_config("config.yaml")
    # Set paths to temp directories to avoid writing to project root during tests
    config_data.pipeline.db_path = ":memory:"

    # Write a temporary resume file for testing
    temp_resume = tmp_path / "resume.typ"
    temp_resume.write_text("= Vineet Kushwaha Resume")
    config_data.pipeline.base_resume_path = str(temp_resume)
    config_data.pipeline.generated_resumes_dir = str(tmp_path / "generated")

    # 3. Create runner with injected mocks
    runner = PipelineRunner()
    runner.config = config_data
    runner.SessionLocal = session_factory
    runner.llm = MockLLMProvider()
    runner.browser = MockBrowserProvider()
    runner.gmail = MockGmailProvider()

    # 4. Run pipeline stages
    _run_id = runner.run()

    # 5. Assert states in database
    db_apps = session.query(Application).all()
    assert len(db_apps) == 1
    app = db_apps[0]

    assert app.state == "Completed"
    assert app.current_stage == 12
    assert app.score == pytest.approx(0.88, abs=0.01)  # Calculated based on mock scores

    # Verify related entities
    assert app.job.title == "Software Engineer"
    assert app.job.company.name == "MockTech"
    assert app.contact.name == "Alice Developer"
    assert app.contact.email == "alice@mocktech.com"

    # Verify resume file generated
    assert app.tailored_resume_path is not None
    assert os.path.exists(app.tailored_resume_path)

    # Verify email and draft ID saved
    email_entry = session.query(Email).filter(Email.application_id == app.id).first()
    assert email_entry is not None
    assert email_entry.gmail_draft_id == "draft_abc123"
    assert email_entry.status == "draft_created"

    session.close()
