import os
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    Markdown,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from src.config import AppConfig, load_config
from src.db.models import (
    Application,
    Company,
    Contact,
    Email,
    History,
    Job,
    ResumeVersion,
)
from src.db.session import get_session_factory
from src.pipeline.runner import PipelineRunner


class RecruitingApp(App[Any]):
    """
    A professional, premium Textual Terminal UI for the Recruiting Platform.
    """

    CSS = """
    Screen {
        background: #121214;
        color: #e2e8f0;
    }
    
    #header {
        background: #1e1e24;
        color: #38bdf8;
        text-align: center;
        height: 3;
        border-bottom: solid #38bdf8;
    }
    
    #dashboard-grid {
        grid-size: 4 1;
        grid-gutter: 1;
        height: 6;
        margin: 1;
    }
    
    .stat-card {
        background: #1a1b26;
        border: solid #2f343f;
        padding: 1;
        align: center middle;
        text-align: center;
    }
    
    .stat-title {
        color: #94a3b8;
        font-size: 85%;
        text-transform: uppercase;
        margin-bottom: 1;
    }
    
    .stat-value {
        color: #38bdf8;
        font-weight: bold;
        font-size: 140%;
    }
    
    .button-bar {
        height: auto;
        margin: 1;
        background: #1a1b26;
        border: solid #2f343f;
        padding: 1;
    }
    
    Button {
        margin-right: 1;
        background: #38bdf8;
        color: #121214;
    }
    
    Button:hover {
        background: #0ea5e9;
    }
    
    Button#btn-retry {
        background: #f59e0b;
    }
    
    Button#btn-run {
        background: #10b981;
    }
    
    DataTable {
        background: #1a1b26;
        border: solid #2f343f;
        height: 1fr;
        margin: 1;
    }
    
    #details-panel {
        background: #1a1b26;
        border: solid #2f343f;
        height: 1fr;
        margin: 1;
        padding: 1;
        overflow-y: scroll;
    }
    
    RichLog {
        background: #0f172a;
        color: #cbd5e1;
        border: solid #334155;
        height: 1fr;
        margin: 1;
    }

    #app-list-container {
        width: 70fr;
    }

    #app-details-container {
        width: 30fr;
    }

    .section-title {
        margin: 1 2;
        font-weight: bold;
    }
    """

    TITLE = "Antigravity Recruiting Board"
    SUB_TITLE = "Extensible Cold-Email Automator"

    def __init__(self, config_path: str = "config.yaml"):
        super().__init__()
        self.config_path = config_path
        self.config: AppConfig = load_config(config_path)
        self.runner = PipelineRunner(config_path)
        self.SessionLocal = get_session_factory(self.config.pipeline.db_path)
        self.selected_app_id: int | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with TabbedContent():
            # --- DASHBOARD TAB ---
            with TabPane("Dashboard", id="tab-dashboard"):
                with Grid(id="dashboard-grid"):
                    with Vertical(classes="stat-card"):
                        yield Label("Total Applications", classes="stat-title")
                        yield Label("0", id="stat-total", classes="stat-value")
                    with Vertical(classes="stat-card"):
                        yield Label("Gmail Drafts Created", classes="stat-title")
                        yield Label("0", id="stat-completed", classes="stat-value")
                    with Vertical(classes="stat-card"):
                        yield Label("Failed Pipeline Steps", classes="stat-title")
                        yield Label("0", id="stat-failed", classes="stat-value")
                    with Vertical(classes="stat-card"):
                        yield Label("Excluded / Skipped", classes="stat-title")
                        yield Label("0", id="stat-filtered", classes="stat-value")

                with Horizontal(classes="button-bar"):
                    yield Button("Run Pipeline Iteration", id="btn-run")
                    yield Button("Retry Failed Stages", id="btn-retry")
                    yield Button("Refresh Metrics & Tables", id="btn-refresh")

                yield Label(
                    "[bold cyan] Active Applications Runtime Progress:[/bold cyan]",
                    classes="section-title",
                )
                yield DataTable(id="table-dashboard-apps")

            # --- APPLICATIONS TAB ---
            with TabPane("Applications", id="tab-applications"):
                with Horizontal():
                    with Vertical(id="app-list-container"):
                        yield DataTable(id="table-applications-list")
                    with Vertical(id="app-details-container"):
                        yield Label(
                            "[bold yellow] Application Detail Inspector [/bold yellow]",
                            classes="section-title",
                        )
                        with Container(id="details-panel"):
                            yield Static(
                                "Select an application from the table to view details.",
                                id="detail-text",
                            )

            # --- DATABASE EXPLORER TAB ---
            with TabPane("Browse Companies/Jobs", id="tab-db-explorer"):
                with TabbedContent():
                    with TabPane("Companies"):
                        yield DataTable(id="table-companies")
                    with TabPane("Contacts"):
                        yield DataTable(id="table-contacts")
                    with TabPane("Jobs"):
                        yield DataTable(id="table-jobs")

            # --- CONFIG & LOGS TAB ---
            with TabPane("Config & Logs", id="tab-logs"), Horizontal():
                with Vertical():
                    yield Label(
                        "[bold cyan] Active YAML Configuration [/bold cyan]",
                        classes="section-title",
                    )
                    yield Markdown(id="markdown-config")
                with Vertical():
                    yield Label(
                        "[bold orange3] Pipeline Activity Log File [/bold orange3]",
                        classes="section-title",
                    )
                    yield RichLog(id="log-viewer", highlight=True)

        yield Footer()

    def on_mount(self) -> None:
        self.refresh_all_data()
        self.load_config_markdown()
        self.tail_log_file()

    def refresh_all_data(self) -> None:
        session = self.SessionLocal()
        try:
            # 1. Update stats
            total_apps = session.query(Application).count()
            completed_apps = (
                session.query(Application)
                .filter(Application.state == "Completed")
                .count()
            )
            failed_apps = (
                session.query(Application)
                .filter(
                    Application.state.in_(
                        [
                            "Failed",
                            "Research Failed",
                            "Draft Failed",
                            "Validation Failed",
                        ]
                    )
                )
                .count()
            )
            filtered_apps = (
                session.query(Application)
                .filter(
                    Application.state.in_(
                        ["Excluded Company", "Salary Too Low", "Ghost Job"]
                    )
                )
                .count()
            )

            self.query_one("#stat-total", Label).update(str(total_apps))
            self.query_one("#stat-completed", Label).update(str(completed_apps))
            self.query_one("#stat-failed", Label).update(str(failed_apps))
            self.query_one("#stat-filtered", Label).update(str(filtered_apps))

            # 2. Populate active apps in dashboard
            active_table = self.query_one("#table-dashboard-apps", DataTable)
            active_table.clear(columns=True)
            active_table.add_columns(
                "App ID",
                "Company",
                "Job Title",
                "Stage",
                "Current State",
                "Last Updated",
            )

            terminal_states = [
                "Completed",
                "Skipped",
                "Duplicate",
                "Salary Too Low",
                "Excluded Company",
                "Ghost Job",
                "Failed",
            ]
            active_apps = (
                session.query(Application)
                .filter(Application.state.notin_(terminal_states))
                .order_by(Application.updated_at.desc())
                .all()
            )

            for app in active_apps:
                active_table.add_row(
                    str(app.id),
                    app.job.company.name,
                    app.job.title,
                    f"Stage {app.current_stage}",
                    app.state,
                    app.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                )

            # 3. Populate applications list tab
            app_list_table = self.query_one("#table-applications-list", DataTable)
            app_list_table.clear(columns=True)
            app_list_table.add_columns(
                "ID",
                "Company",
                "Title",
                "Stage",
                "State",
                "Score",
                "Email",
                "Resume Path",
            )

            all_apps = (
                session.query(Application).order_by(Application.updated_at.desc()).all()
            )
            for app in all_apps:
                score_str = f"{app.score:.2f}" if app.score else "N/A"
                email_str = (
                    app.contact.email if app.contact and app.contact.email else "N/A"
                )
                res_path = (
                    os.path.basename(app.tailored_resume_path)
                    if app.tailored_resume_path
                    else "N/A"
                )
                app_list_table.add_row(
                    str(app.id),
                    app.job.company.name,
                    app.job.title,
                    str(app.current_stage),
                    app.state,
                    score_str,
                    email_str,
                    res_path,
                )

            # 4. Populate companies list
            comp_table = self.query_one("#table-companies", DataTable)
            comp_table.clear(columns=True)
            comp_table.add_columns(
                "ID", "Company Name", "Domain", "Employees", "Industry"
            )
            for c in session.query(Company).limit(100).all():
                comp_table.add_row(
                    str(c.id),
                    c.name,
                    c.domain or "N/A",
                    str(c.employee_count or "N/A"),
                    c.industry or "N/A",
                )

            # 5. Populate contacts list
            con_table = self.query_one("#table-contacts", DataTable)
            con_table.clear(columns=True)
            con_table.add_columns("ID", "Company", "Name", "Role", "Email")
            for ct in session.query(Contact).limit(100).all():
                con_table.add_row(
                    str(ct.id), ct.company.name, ct.name, ct.role, ct.email or "N/A"
                )

            # 6. Populate jobs list
            job_table = self.query_one("#table-jobs", DataTable)
            job_table.clear(columns=True)
            job_table.add_columns("ID", "Company", "Title", "Location", "Salary")
            for j in session.query(Job).limit(100).all():
                job_table.add_row(
                    str(j.id),
                    j.company.name,
                    j.title,
                    j.location or "N/A",
                    j.salary or "N/A",
                )

        finally:
            session.close()

    def load_config_markdown(self) -> None:
        if os.path.exists(self.config_path):
            with open(self.config_path) as f:
                content = f.read()
            md_text = f"```yaml\n{content}\n```"
            self.query_one("#markdown-config", Markdown).update(md_text)

    def tail_log_file(self) -> None:
        log_viewer = self.query_one("#log-viewer", RichLog)
        log_file_path = "logs/platform.log"
        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, encoding="utf-8") as f:
                    lines = f.readlines()[-100:]  # Last 100 logs
                    for line in lines:
                        log_viewer.write(line.strip())
            except Exception as e:
                log_viewer.write(f"Error reading log file: {e}")
        else:
            log_viewer.write(
                "No active logs yet. Start the pipeline to see logging details."
            )

    # --- Button actions ---
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-refresh":
            self.refresh_all_data()
            self.tail_log_file()
        elif button_id == "btn-run":
            self.run_pipeline_async()
        elif button_id == "btn-retry":
            self.retry_pipeline_async()

    def run_pipeline_async(self) -> None:
        self.notify("Executing Pipeline Run in background...")
        # Since Textual executes in loop, run in background or inline if lightweight.
        # Running inline is fine but blocks rendering slightly. Let's execute runner run:
        try:
            self.runner.run(max_stage=12)
            self.notify("Pipeline run completed!")
        except Exception as e:
            self.notify(f"Pipeline crashed: {e}", severity="error")
        self.refresh_all_data()
        self.tail_log_file()

    def retry_pipeline_async(self) -> None:
        self.notify("Retrying failed applications...")
        try:
            self.runner.retry_failed()
            self.notify("Retry run completed!")
        except Exception as e:
            self.notify(f"Retry failed: {e}", severity="error")
        self.refresh_all_data()
        self.tail_log_file()

    # --- DataTable selection/inspect details ---
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table_id = event.data_table.id
        if table_id == "table-applications-list":
            # Extract App ID from the first cell
            row_key = event.row_key
            row = event.data_table.get_row(row_key)
            app_id = int(row[0])
            self.inspect_application_details(app_id)

    def inspect_application_details(self, app_id: int) -> None:
        session = self.SessionLocal()
        try:
            app = session.query(Application).filter(Application.id == app_id).first()
            if not app:
                return

            email_info = (
                session.query(Email)
                .filter(Email.application_id == app.id)
                .order_by(Email.id.desc())
                .first()
            )
            res_info = (
                session.query(ResumeVersion)
                .filter(ResumeVersion.application_id == app.id)
                .order_by(ResumeVersion.id.desc())
                .first()
            )
            history_info = (
                session.query(History)
                .filter(History.application_id == app.id)
                .order_by(History.timestamp.desc())
                .all()
            )

            # Format inspect details
            details_str = f"**Application #{app.id} details:**\n\n"
            details_str += f"- **Company**: {app.job.company.name}\n"
            details_str += f"- **Job Title**: {app.job.title}\n"
            details_str += f"- **State**: {app.state} (Stage {app.current_stage})\n"
            details_str += (
                f"- **Weighted Score**: {f'{app.score:.2f}' if app.score else 'N/A'}\n"
            )
            if app.score_breakdown:
                details_str += f"  - Breakdown: {app.score_breakdown}\n"
            details_str += f"- **Resume Path**: {app.tailored_resume_path or 'N/A'}\n\n"

            if res_info:
                details_str += "**Resume Tailoring Decision:**\n"
                details_str += f"- Keywords Added: {res_info.keywords_added}\n"
                details_str += f"- Reasoning: {res_info.reasoning}\n\n"

            if email_info:
                details_str += "**Outreach Email:**\n"
                details_str += f"- Subject: {email_info.subject}\n"
                details_str += (
                    f"- Gmail Draft ID: {email_info.gmail_draft_id or 'N/A'}\n"
                )
                details_str += f"- HTML Body Preview:\n\n{email_info.body[:2000]}\n\n"

            if history_info:
                details_str += "**State Machine History:**\n"
                for h in history_info:
                    details_str += f"- [{h.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Stage {h.stage}: {h.state} - {h.notes or ''}\n"

            # Update the panel content
            # Wait, our panel content is a Static widget inside details-panel container. Let's retrieve it:
            self.query_one("#detail-text", Static).update(details_str)

        finally:
            session.close()
