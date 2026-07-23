import os

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.db.models import Application, Run
from src.db.session import get_session_factory
from src.db.session import init_db as db_init
from src.pipeline.runner import PipelineRunner

app = typer.Typer(help="AI-assisted Recruiting Platform CLI")
console = Console()


def get_runner(config_path: str = "config.yaml") -> PipelineRunner:
    """Helper to initialize PipelineRunner with error handling."""
    if not os.path.exists(config_path):
        console.print(f"[bold red]Error:[/bold red] Config file '{config_path}' not found. Please create one.")
        raise typer.Exit(code=1)
    try:
        return PipelineRunner(config_path)
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        raise typer.Exit(code=1) from e


def auto_start_widget(config_path: str = "config.yaml") -> None:
    """Auto-launches dark mode status widget server on port 18492 if not already running."""
    try:
        from src.config import load_config
        from src.web_server import DEFAULT_WIDGET_PORT, ensure_widget_server_running

        cfg = load_config(config_path)
        ensure_widget_server_running(db_path=cfg.pipeline.db_path, port=DEFAULT_WIDGET_PORT, auto_open=True)
    except Exception as e:
        console.print(f"[yellow]Widget auto-start warning: {e}[/yellow]")


@app.command("run")
def run_pipeline(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
    limit: int | None = typer.Option(None, help="Override daily draft limit"),
) -> None:
    """
    Run the entire recruiting pipeline end-to-end (discover, filter, research, tailor, draft).
    """
    auto_start_widget(config)
    console.print("[bold green]Starting Recruiting Platform End-to-End Pipeline...[/bold green]")
    runner = get_runner(config)
    try:
        run_id = runner.run(max_stage=12, limit_drafts=limit)
        console.print(f"[bold green]Pipeline completed successfully for {run_id}![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Pipeline failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command("targeted")
def run_targeted_outreach(
    target: str = typer.Argument(..., help="Company name, company email, domain, or related identifier"),
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
    jd: str | None = typer.Option(None, help="Pasted Job Description text"),
) -> None:
    """
    Run targeted search, research, and outreach for a specific company or contact.
    """
    if not jd:
        import os
        jd = os.environ.get("JD")
        # Clean up empty strings or whitespace-only inputs
        if jd and not jd.strip():
            jd = None

    console.print(f"[bold green]Starting Targeted Outreach for: '{target}'...[/bold green]")
    runner = get_runner(config)
    try:
        run_id = runner.run_targeted(target, jd=jd, max_stage=12)
        console.print(f"[bold green]Targeted outreach completed successfully for {run_id}![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Targeted outreach failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command("search")
def search_jobs(config: str = typer.Option("config.yaml", help="Path to config.yaml")) -> None:
    """
    Stage 0 - 2: Search for jobs, discover companies, and apply filtering criteria.
    """
    console.print("[bold cyan]Executing Job & Company Discovery (Stages 0-2)...[/bold cyan]")
    runner = get_runner(config)
    try:
        run_id = runner.run(max_stage=2)
        console.print(
            f"[bold green]Discovery completed for {run_id}. Applications initialized and filtered.[/bold green]"
        )
    except Exception as e:
        console.print(f"[bold red]Discovery failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command("research")
def research_companies(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """
    Stage 3 - 5: Gather research on filtered companies and discover contacts & email patterns.
    """
    console.print("[bold magenta]Executing Research and Contact Discovery (Stages 3-5)...[/bold magenta]")
    runner = get_runner(config)
    try:
        run_id = runner.run(resume_only=True, max_stage=5)
        console.print(f"[bold green]Research completed for {run_id}. Contacts and email profiles added.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Research failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command("tailor")
def tailor_resumes(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """
    Stage 6 - 7: Score opportunities and generate tailored Typst resumes.
    """
    console.print("[bold yellow]Executing Opportunity Scoring & Resume Tailoring (Stages 6-7)...[/bold yellow]")
    runner = get_runner(config)
    try:
        run_id = runner.run(resume_only=True, max_stage=7)
        console.print(
            f"[bold green]Resume tailoring completed for {run_id}. Output saved in resumes/generated.[/bold green]"
        )
    except Exception as e:
        console.print(f"[bold red]Resume tailoring failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command("draft")
def create_drafts(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
    limit: int | None = typer.Option(None, help="Override daily draft limit"),
) -> None:
    """
    Stage 8 - 10: Generate personalized emails, validate content, and save Gmail drafts.
    """
    console.print("[bold blue]Executing Email Generation & Gmail Draft Creation (Stages 8-10)...[/bold blue]")
    runner = get_runner(config)
    try:
        run_id = runner.run(resume_only=True, max_stage=10, limit_drafts=limit)
        console.print(f"[bold green]Draft generation completed for {run_id}. Gmail drafts populated.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Drafting failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command("resume")
def resume_pipeline(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """
    Resume processing all paused/interrupted applications from their saved stage.
    """
    console.print("[bold green]Resuming Pipeline for Pause-State Applications...[/bold green]")
    runner = get_runner(config)
    try:
        run_id = runner.run(resume_only=True, max_stage=12)
        console.print(f"[bold green]Resumed pipeline runs finished for {run_id}.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Resume execution failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command("retry")
def retry_failed_applications(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """
    Reset applications in failed states (Failed, Draft Failed, etc.) and retry them.
    """
    console.print("[bold orange3]Retrying failed pipeline stages...[/bold orange3]")
    runner = get_runner(config)
    try:
        run_id = runner.retry_failed()
        console.print(f"[bold green]Retry run finished for {run_id}.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Retry process failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e



@app.command("auth")
def authenticate_gmail(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """
    Authenticate Gmail API connection interactively to generate token.json.
    """
    console.print("[bold cyan]Starting interactive Gmail authentication...[/bold cyan]")
    runner = get_runner(config)
    success = runner.gmail.authenticate(interactive=True)
    if success:
        console.print("[bold green]Gmail authentication completed successfully! Credentials saved.[/bold green]")
    else:
        console.print("[bold red]Gmail authentication failed.[/bold red]")
        raise typer.Exit(code=1)


@app.command("init-db")
def initialize_database(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """
    Initialize SQLite database tables.
    """
    runner = get_runner(config)
    db_path = runner.config.pipeline.db_path
    console.print(f"[bold green]Initializing SQLite database at: {db_path}[/bold green]")
    try:
        db_init(db_path)
        console.print("[bold green]Database tables created successfully.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Database initialization failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command("config-summary")
def config_summary(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """
    Print a summary of active configurations and preferences.
    """
    runner = get_runner(config)
    cfg = runner.config

    table = Table(
        title="Recruiting Platform Configuration Summary",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")

    table.add_row("Database Path", cfg.pipeline.db_path)
    table.add_row("Base Resume Path", cfg.pipeline.base_resume_path)
    table.add_row("Roles Pref", ", ".join(cfg.job_preferences.roles))
    table.add_row("Geographies", ", ".join(cfg.job_preferences.geographies))
    table.add_row("Salary Min LPA", f"{cfg.job_preferences.salary_range.min_lpa} LPA")
    table.add_row("Salary Max LPA", f"{cfg.job_preferences.salary_range.max_lpa} LPA")
    table.add_row(
        "Company Size (Employees)",
        f"{cfg.job_preferences.company_size.min_employees} - {cfg.job_preferences.company_size.max_employees}",
    )
    table.add_row("Daily Draft Limit", str(cfg.pipeline.daily_draft_limit))
    table.add_row("LLM Provider", cfg.llm.provider)
    table.add_row("LLM Model", cfg.llm.model)
    table.add_row("Cache Lifetime (seconds)", str(cfg.pipeline.cache_lifetime_seconds))

    console.print(table)


@app.command("status")
def view_status(config: str = typer.Option("config.yaml", help="Path to config.yaml")) -> None:
    """
    View current status and statistics of job applications.
    """
    runner = get_runner(config)
    session_factory = get_session_factory(runner.config.pipeline.db_path)
    session = session_factory()

    try:
        total_apps = session.query(Application).count()
        completed_apps = session.query(Application).filter(Application.state == "Completed").count()
        failed_apps = (
            session.query(Application)
            .filter(Application.state.in_(["Failed", "Research Failed", "Draft Failed", "Validation Failed"]))
            .count()
        )
        filtered_apps = (
            session.query(Application)
            .filter(Application.state.in_(["Excluded Company", "Salary Too Low", "Ghost Job"]))
            .count()
        )

        panel_content = (
            f"[bold cyan]Total Applications Tracked:[/bold cyan] {total_apps}\n"
            f"[bold green]Drafts Completed & Finalized:[/bold green] {completed_apps}\n"
            f"[bold red]Failed Processing Stages:[/bold red] {failed_apps}\n"
            f"[bold yellow]Filtered Out / Excluded:[/bold yellow] {filtered_apps}\n\n"
            f"[bold]Active runs in progress:[/bold] {session.query(Run).filter(Run.status == 'running').count()}"
        )
        console.print(Panel(panel_content, title="Recruiting Pipeline Dashboard", expand=False))

        # Display recent 10 applications
        if total_apps > 0:
            app_table = Table(
                title="Recent Job Applications",
                show_header=True,
                header_style="bold blue",
            )
            app_table.add_column("ID", style="dim")
            app_table.add_column("Company", style="bold")
            app_table.add_column("Job Title", style="cyan")
            app_table.add_column("Stage", style="magenta")
            app_table.add_column("State/Terminal Status", style="green")
            app_table.add_column("Score", style="yellow")

            recent = session.query(Application).order_by(Application.updated_at.desc()).limit(10).all()
            for app in recent:
                score_str = f"{app.score:.2f}" if app.score else "N/A"
                app_table.add_row(
                    str(app.id),
                    app.job.company.name,
                    app.job.title,
                    f"Stage {app.current_stage}",
                    app.state,
                    score_str,
                )
            console.print(app_table)

    finally:
        session.close()



@app.command("widget")
def start_widget(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
    port: int = typer.Option(18492, help="Port to serve dark mode widget on"),
    host: str = typer.Option("127.0.0.1", help="Host address"),
) -> None:
    """
    Launch minimal dark mode job status widget web server on uncommon port (positioned top-right / bottom-right).
    """
    from src.config import load_config
    from src.web_server import run_widget_server

    cfg = load_config(config)
    db_path = cfg.pipeline.db_path
    console.print(f"[bold cyan]Starting Minimal Dark Mode Status Widget at http://{host}:{port}...[/bold cyan]")
    run_widget_server(db_path=db_path, port=port, host=host)


@app.command("export")
def export_data(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
    all_records: bool = typer.Option(False, "--all", help="Export all records, bypassing incremental manifest"),
    dir: str = typer.Option("exports", help="Target export directory"),
) -> None:
    """
    Incrementally export outreach data (company & email details) to JSON & CSV.
    """
    from src.config import load_config
    from src.utils.exporter import export_outreach_data

    cfg = load_config(config)
    console.print("[bold cyan]Executing Incremental Outreach Data Export...[/bold cyan]")
    res = export_outreach_data(db_path=cfg.pipeline.db_path, export_dir=dir, export_all=all_records)
    if res.get("exported_count", 0) > 0:
        console.print(f"[bold green]{res['message']}[/bold green]")
        console.print(f"[dim]Latest CSV file: {res['latest_csv_path']}[/dim]")
    else:
        console.print(f"[bold yellow]{res['message']}[/bold yellow]")


@app.command("clean-invalid")
def clean_invalid(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """
    Clean invalid email IDs and non-working application states (NEVER deletes company/job/contact/email records).
    """
    from src.config import load_config
    from src.utils.cleaner import clean_invalid_emails_and_states

    cfg = load_config(config)
    console.print("[bold magenta]Cleaning invalid contact email IDs and non-working states...[/bold magenta]")
    res = clean_invalid_emails_and_states(db_path=cfg.pipeline.db_path)
    console.print(f"[bold green]{res['message']}[/bold green]")


if __name__ == "__main__":
    app()
