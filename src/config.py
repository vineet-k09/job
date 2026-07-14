import os

import yaml
from pydantic import BaseModel


class SalaryRange(BaseModel):
    min_lpa: float
    max_lpa: float


class CompanySize(BaseModel):
    min_employees: int
    max_employees: int


class JobPreferences(BaseModel):
    roles: list[str]
    geographies: list[str]
    remote_only: bool
    salary_range: SalaryRange
    company_size: CompanySize
    experience_years_max: float
    allow_speculative_outreach: bool = False


class Exclusions(BaseModel):
    companies: list[str]
    keywords: list[str]


class PipelineSettings(BaseModel):
    daily_draft_limit: int
    research_depth: str
    cache_lifetime_seconds: int
    retry_limits: int
    base_resume_path: str
    generated_resumes_dir: str
    db_path: str


class LLMConfig(BaseModel):
    provider: str
    model: str
    api_key: str = ""
    api_url: str = ""
    temperature: float = 0.2
    max_tokens: int = 1000


class GmailConfig(BaseModel):
    credentials_file: str
    token_file: str
    scopes: list[str]


class ScoringWeights(BaseModel):
    role_match: float
    tech_stack: float
    salary: float
    company_quality: float
    growth: float
    confidence: float


class ScoringThresholds(BaseModel):
    minimum_score: float


class ScoringConfig(BaseModel):
    weights: ScoringWeights
    thresholds: ScoringThresholds


class PromptTemplates(BaseModel):
    company_research: str
    resume_tailoring: str
    email_generation: str


class AppConfig(BaseModel):
    job_preferences: JobPreferences
    exclusions: Exclusions
    pipeline: PipelineSettings
    llm: LLMConfig
    gmail: GmailConfig
    scoring: ScoringConfig
    prompts: PromptTemplates


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """Loads configuration from a YAML file and validates it using Pydantic."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    return AppConfig(**config_data)
