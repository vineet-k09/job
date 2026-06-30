from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running")  # running, completed, failed

    applications: Mapped[list["Application"]] = relationship(back_populates="run")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    research_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    jobs: Mapped[list["Job"]] = relationship(back_populates="company")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    salary: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_min_lpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max_lpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    experience_years_required: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="jobs")
    applications: Mapped[list["Application"]] = relationship(back_populates="job")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    linkedin_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="contacts")
    applications: Mapped[list["Application"]] = relationship(back_populates="contact")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("runs.id"), index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), index=True)
    contact_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("contacts.id"), nullable=True)
    current_stage: Mapped[int] = mapped_column(Integer, default=0)  # 0 to 12
    state: Mapped[str] = mapped_column(String, default="Company Discovery")  # Terminal states or stages
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    tailored_resume_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    run: Mapped[Run] = relationship(back_populates="applications")
    job: Mapped[Job] = relationship(back_populates="applications")
    contact: Mapped[Contact | None] = relationship(back_populates="applications")
    emails: Mapped[list["Email"]] = relationship(back_populates="application")
    resume_versions: Mapped[list["ResumeVersion"]] = relationship(back_populates="application")
    history_records: Mapped[list["History"]] = relationship(back_populates="application")


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), index=True)
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    gmail_draft_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft_created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    application: Mapped[Application] = relationship(back_populates="emails")


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), index=True)
    parent_resume: Mapped[str] = mapped_column(String)
    company: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    keywords_added: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    application: Mapped[Application] = relationship(back_populates="resume_versions")


class History(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), index=True)
    stage: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("runs.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped[Application] = relationship(back_populates="history_records")


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
