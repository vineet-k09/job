import contextlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

DEFAULT_WIDGET_PORT = 18492

STAGE_NAMES = {
    0: "Company Discovery",
    1: "Job Discovery",
    2: "Filtering & Screening",
    3: "Company Research",
    4: "Contact Research",
    5: "Email Discovery",
    6: "Opportunity Scoring",
    7: "Resume Tailoring",
    8: "Email Generation",
    9: "Validation & QC",
    10: "Gmail Draft Creation",
    11: "DB Finalization",
    12: "Completed",
}

TERMINAL_STATES = (
    "Completed",
    "Skipped",
    "Duplicate",
    "Salary Too Low",
    "Excluded Company",
    "Ghost Job",
    "Failed",
    "No Professional Email",
)

# Global status tracking for async actions
_action_lock = threading.Lock()
_action_state = {
    "is_running": False,
    "current_action": None,
    "last_message": "Idle",
    "error": None,
}


def get_db_status(db_path: str) -> dict[str, Any]:
    """Retrieve job application status summary from SQLite database."""
    if not os.path.exists(db_path):
        return {
            "error": f"Database file not found at {db_path}",
            "active_jobs_count": 0,
            "jobs": [],
            "summary": {"total": 0, "completed": 0, "failed": 0, "filtered": 0, "active": 0},
            "action_status": _action_state,
        }

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Summary counts
        cur.execute("SELECT COUNT(*) as total FROM applications")
        total = cur.fetchone()["total"]

        cur.execute(
            """
            SELECT COUNT(*) as completed FROM applications 
            WHERE state = 'Completed' OR id IN (SELECT application_id FROM emails WHERE gmail_draft_id IS NOT NULL)
            """
        )
        completed = cur.fetchone()["completed"]

        cur.execute(
            """
            SELECT COUNT(*) as failed FROM applications 
            WHERE state LIKE '%Failed%' OR state LIKE '%Error%'
            """
        )
        failed = cur.fetchone()["failed"]

        cur.execute(
            """
            SELECT COUNT(*) as filtered FROM applications
            WHERE state IN ('Excluded Company', 'Salary Too Low', 'Ghost Job', 'Duplicate', 'No Professional Email', 'Skipped')
            """
        )
        filtered = cur.fetchone()["filtered"]

        # Active running applications
        cur.execute(
            """
            SELECT a.id, a.run_id, a.current_stage, a.state, a.updated_at, a.score,
                   j.title as job_title, c.name as company_name
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN companies c ON j.company_id = c.id
            WHERE a.state NOT IN (?, ?, ?, ?, ?, ?, ?, ?)
            ORDER BY a.updated_at DESC
            """,
            TERMINAL_STATES,
        )
        active_rows = cur.fetchall()

        jobs = []
        for r in active_rows:
            stage_num = r["current_stage"]
            stage_name = STAGE_NAMES.get(stage_num, r["state"])
            percent = int((stage_num / 12.0) * 100) if stage_num <= 12 else 100
            jobs.append(
                {
                    "id": r["id"],
                    "run_id": r["run_id"],
                    "company_name": r["company_name"],
                    "job_title": r["job_title"],
                    "current_stage": stage_num,
                    "stage_name": stage_name,
                    "stage_percent": percent,
                    "state": r["state"],
                    "updated_at": str(r["updated_at"]),
                    "score": round(r["score"], 2) if r["score"] else None,
                }
            )

        # Active runs count
        cur.execute("SELECT COUNT(*) as active_runs FROM runs WHERE status = 'running'")
        active_runs_res = cur.fetchone()
        active_runs = active_runs_res["active_runs"] if active_runs_res else 0

        conn.close()

        return {
            "active_jobs_count": len(jobs),
            "active_runs_count": active_runs,
            "summary": {
                "total": total,
                "completed": completed,
                "failed": failed,
                "filtered": filtered,
                "active": len(jobs),
            },
            "jobs": jobs,
            "action_status": _action_state,
        }
    except Exception as e:
        return {
            "error": str(e),
            "active_jobs_count": 0,
            "jobs": [],
            "summary": {"total": 0, "completed": 0, "failed": 0, "filtered": 0, "active": 0},
            "action_status": _action_state,
        }


def get_all_applications(db_path: str) -> list[dict[str, Any]]:
    """Retrieve full list of applications for table view."""
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT a.id, a.run_id, a.current_stage, a.state, a.score, a.tailored_resume_path, a.updated_at,
                   j.title as job_title, c.name as company_name, ct.email as contact_email
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN companies c ON j.company_id = c.id
            LEFT JOIN contacts ct ON a.contact_id = ct.id
            ORDER BY a.updated_at DESC
            """
        )
        rows = cur.fetchall()
        apps = []
        for r in rows:
            stage_num = r["current_stage"]
            res_filename = os.path.basename(r["tailored_resume_path"]) if r["tailored_resume_path"] else None
            apps.append(
                {
                    "id": r["id"],
                    "run_id": r["run_id"],
                    "company_name": r["company_name"],
                    "job_title": r["job_title"],
                    "current_stage": stage_num,
                    "stage_name": STAGE_NAMES.get(stage_num, r["state"]),
                    "state": r["state"],
                    "score": round(r["score"], 2) if r["score"] is not None else None,
                    "contact_email": r["contact_email"] or "N/A",
                    "resume_path": r["tailored_resume_path"] or "N/A",
                    "resume_file": res_filename or "N/A",
                    "updated_at": str(r["updated_at"]),
                }
            )
        conn.close()
        return apps
    except Exception:
        return []


def get_application_details(db_path: str, app_id: int) -> dict[str, Any] | None:
    """Retrieve complete application inspection details."""
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT a.id, a.run_id, a.current_stage, a.state, a.score, a.score_breakdown,
                   a.tailored_resume_path, a.created_at, a.updated_at,
                   j.title as job_title, j.location as job_location, j.salary as job_salary, j.description as job_description,
                   c.name as company_name, c.domain as company_domain, c.industry as company_industry, c.employee_count as company_employees,
                   ct.name as contact_name, ct.role as contact_role, ct.email as contact_email
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN companies c ON j.company_id = c.id
            LEFT JOIN contacts ct ON a.contact_id = ct.id
            WHERE a.id = ?
            """,
            (app_id,),
        )
        app_row = cur.fetchone()
        if not app_row:
            conn.close()
            return None

        # Parse score breakdown
        breakdown = None
        if app_row["score_breakdown"]:
            try:
                breakdown = json.loads(app_row["score_breakdown"])
            except Exception:
                breakdown = app_row["score_breakdown"]

        # Fetch latest email
        cur.execute(
            """
            SELECT subject, body, gmail_draft_id, status, scheduled_at, created_at
            FROM emails WHERE application_id = ? ORDER BY id DESC LIMIT 1
            """,
            (app_id,),
        )
        email_row = cur.fetchone()
        email_info = None
        if email_row:
            email_info = {
                "subject": email_row["subject"],
                "body": email_row["body"],
                "gmail_draft_id": email_row["gmail_draft_id"],
                "status": email_row["status"],
                "scheduled_at": str(email_row["scheduled_at"]) if email_row["scheduled_at"] else None,
                "created_at": str(email_row["created_at"]),
            }

        # Fetch latest resume version
        cur.execute(
            """
            SELECT parent_resume, company, role, keywords_added, reasoning, path, created_at
            FROM resume_versions WHERE application_id = ? ORDER BY id DESC LIMIT 1
            """,
            (app_id,),
        )
        res_row = cur.fetchone()
        resume_info = None
        if res_row:
            kw_added = res_row["keywords_added"]
            if isinstance(kw_added, str):
                with contextlib.suppress(Exception):
                    kw_added = json.loads(kw_added)
            resume_info = {
                "parent_resume": res_row["parent_resume"],
                "company": res_row["company"],
                "role": res_row["role"],
                "keywords_added": kw_added,
                "reasoning": res_row["reasoning"],
                "path": res_row["path"],
                "created_at": str(res_row["created_at"]),
            }

        # Fetch history records
        cur.execute(
            """
            SELECT stage, state, timestamp, notes FROM history
            WHERE application_id = ? ORDER BY timestamp DESC
            """,
            (app_id,),
        )
        history_rows = cur.fetchall()
        history_info = [
            {
                "stage": h["stage"],
                "state": h["state"],
                "timestamp": str(h["timestamp"]),
                "notes": h["notes"],
            }
            for h in history_rows
        ]

        conn.close()
        return {
            "id": app_row["id"],
            "run_id": app_row["run_id"],
            "current_stage": app_row["current_stage"],
            "stage_name": STAGE_NAMES.get(app_row["current_stage"], app_row["state"]),
            "state": app_row["state"],
            "score": round(app_row["score"], 2) if app_row["score"] is not None else None,
            "score_breakdown": breakdown,
            "tailored_resume_path": app_row["tailored_resume_path"],
            "created_at": str(app_row["created_at"]),
            "updated_at": str(app_row["updated_at"]),
            "job": {
                "title": app_row["job_title"],
                "location": app_row["job_location"] or "N/A",
                "salary": app_row["job_salary"] or "N/A",
                "description": app_row["job_description"] or "",
            },
            "company": {
                "name": app_row["company_name"],
                "domain": app_row["company_domain"] or "N/A",
                "industry": app_row["company_industry"] or "N/A",
                "employee_count": app_row["company_employees"] or "N/A",
            },
            "contact": {
                "name": app_row["contact_name"] or "N/A",
                "role": app_row["contact_role"] or "N/A",
                "email": app_row["contact_email"] or "N/A",
            },
            "email": email_info,
            "resume": resume_info,
            "history": history_info,
        }
    except Exception:
        return None


def get_companies(db_path: str) -> list[dict[str, Any]]:
    """Retrieve list of companies."""
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name, domain, employee_count, industry, created_at FROM companies ORDER BY name ASC LIMIT 200")
        rows = cur.fetchall()
        res = [
            {
                "id": r["id"],
                "name": r["name"],
                "domain": r["domain"] or "N/A",
                "employee_count": r["employee_count"] or "N/A",
                "industry": r["industry"] or "N/A",
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]
        conn.close()
        return res
    except Exception:
        return []


def get_contacts(db_path: str) -> list[dict[str, Any]]:
    """Retrieve list of contacts."""
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ct.id, ct.name, ct.role, ct.email, ct.linkedin_url, c.name as company_name
            FROM contacts ct
            JOIN companies c ON ct.company_id = c.id
            ORDER BY ct.id DESC LIMIT 200
            """
        )
        rows = cur.fetchall()
        res = [
            {
                "id": r["id"],
                "company_name": r["company_name"],
                "name": r["name"],
                "role": r["role"],
                "email": r["email"] or "N/A",
                "linkedin_url": r["linkedin_url"] or "N/A",
            }
            for r in rows
        ]
        conn.close()
        return res
    except Exception:
        return []


def get_jobs(db_path: str) -> list[dict[str, Any]]:
    """Retrieve list of jobs."""
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT j.id, j.title, j.location, j.salary, c.name as company_name
            FROM jobs j
            JOIN companies c ON j.company_id = c.id
            ORDER BY j.id DESC LIMIT 200
            """
        )
        rows = cur.fetchall()
        res = [
            {
                "id": r["id"],
                "company_name": r["company_name"],
                "title": r["title"],
                "location": r["location"] or "N/A",
                "salary": r["salary"] or "N/A",
            }
            for r in rows
        ]
        conn.close()
        return res
    except Exception:
        return []


def execute_pipeline_action_thread(config_path: str, action_type: str) -> None:
    """Background task runner for pipeline execution."""
    global _action_state
    with _action_lock:
        _action_state["is_running"] = True
        _action_state["current_action"] = action_type
        _action_state["last_message"] = f"Executing {action_type}..."
        _action_state["error"] = None

    try:
        from src.pipeline.runner import PipelineRunner

        runner = PipelineRunner(config_path=config_path)
        if action_type == "run":
            run_id = runner.run(max_stage=12)
            msg = f"Pipeline run completed successfully for {run_id}!"
        elif action_type == "retry":
            run_id = runner.retry_failed()
            msg = f"Retry completed successfully for {run_id}!"
        else:
            msg = f"Unknown action {action_type}"

        with _action_lock:
            _action_state["is_running"] = False
            _action_state["last_message"] = msg
    except Exception as e:
        with _action_lock:
            _action_state["is_running"] = False
            _action_state["error"] = str(e)
            _action_state["last_message"] = f"Action {action_type} failed: {e}"


class StatusWidgetRequestHandler(BaseHTTPRequestHandler):
    db_path: str = "data/platform.db"
    config_path: str = "config.yaml"
    static_dir: Path = Path(__file__).parent / "static"

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP request logs for clean output."""
        return

    def _send_json(self, data: Any, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/status":
            status_data = get_db_status(self.db_path)
            self._send_json(status_data)
            return

        if path == "/api/applications":
            apps_data = get_all_applications(self.db_path)
            self._send_json(apps_data)
            return

        if path == "/api/application_details":
            app_id_str = query_params.get("id", [None])[0]
            if not app_id_str or not app_id_str.isdigit():
                self._send_json({"error": "Missing or invalid application ID"}, 400)
                return
            app_details = get_application_details(self.db_path, int(app_id_str))
            if app_details is None:
                self._send_json({"error": "Application not found"}, 404)
            else:
                self._send_json(app_details)
            return

        if path == "/api/companies":
            comps_data = get_companies(self.db_path)
            self._send_json(comps_data)
            return

        if path == "/api/contacts":
            contacts_data = get_contacts(self.db_path)
            self._send_json(contacts_data)
            return

        if path == "/api/jobs":
            jobs_data = get_jobs(self.db_path)
            self._send_json(jobs_data)
            return

        if path == "/api/config":
            content = ""
            if os.path.exists(self.config_path):
                with open(self.config_path, encoding="utf-8") as f:
                    content = f.read()
            self._send_json({"config": content})
            return

        if path == "/api/logs":
            log_lines = []
            log_path = "logs/platform.log"
            if os.path.exists(log_path):
                try:
                    with open(log_path, encoding="utf-8") as f:
                        log_lines = [line.strip() for line in f.readlines()[-150:]]
                except Exception as e:
                    log_lines = [f"Error reading log file: {e}"]
            else:
                log_lines = ["No active log file found at logs/platform.log."]
            self._send_json({"logs": log_lines})
            return

        # Serve static widget page
        filepath = self.static_dir / "index.html"
        if filepath.exists():
            html_bytes = filepath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_bytes)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/api/actions/run", "/api/actions/retry"):
            action_type = "run" if path == "/api/actions/run" else "retry"
            with _action_lock:
                if _action_state["is_running"]:
                    self._send_json(
                        {
                            "success": False,
                            "message": f"Action '{_action_state['current_action']}' is already running.",
                        },
                        400,
                    )
                    return

            t = threading.Thread(
                target=execute_pipeline_action_thread,
                args=(self.config_path, action_type),
                daemon=True,
            )
            t.start()

            self._send_json(
                {
                    "success": True,
                    "message": f"Action '{action_type}' initiated in background.",
                }
            )
            return

        self._send_json({"error": "Endpoint not found"}, 404)


def is_widget_server_running(port: int = DEFAULT_WIDGET_PORT) -> bool:
    """Check if status widget HTTP server is already running on the given port."""
    try:
        url = f"http://127.0.0.1:{port}/api/status"
        req = urllib.request.Request(url, headers={"User-Agent": "HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return bool(resp.status == 200)
    except Exception:
        return False


def ensure_widget_server_running(
    db_path: str = "data/platform.db",
    config_path: str = "config.yaml",
    port: int = DEFAULT_WIDGET_PORT,
    auto_open: bool = True,
) -> bool:
    """
    Automates widget launching: checks if widget server is active on port 18492.
    If not running, spawns it as a background process and optionally opens it in browser.
    """
    widget_url = f"http://127.0.0.1:{port}"
    if is_widget_server_running(port):
        print(f"★ Job Status Dark Mode Widget already active at {widget_url}")
        return True

    print(f"★ Launching Minimal Dark Mode Job Status Widget on port {port}...")
    try:
        cmd = [sys.executable, "-m", "src.web_server", "--port", str(port), "--db", db_path, "--config", config_path]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if auto_open:
            with contextlib.suppress(Exception):
                webbrowser.open(widget_url)
        return True
    except Exception as e:
        print(f"Could not auto-start widget server: {e}")
        return False


def run_widget_server(
    db_path: str = "data/platform.db",
    config_path: str = "config.yaml",
    port: int = DEFAULT_WIDGET_PORT,
    host: str = "127.0.0.1",
) -> None:
    """Launch HTTP server serving the dark mode job status widget & web dashboard."""
    StatusWidgetRequestHandler.db_path = db_path
    StatusWidgetRequestHandler.config_path = config_path
    server_address = (host, port)
    httpd = HTTPServer(server_address, StatusWidgetRequestHandler)
    print(f"★ Job Status Dark Mode Widget & Web Board running on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Job Status Widget Server...")
        httpd.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Job Status Widget Web Server")
    parser.add_argument("--port", type=int, default=DEFAULT_WIDGET_PORT, help="Port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address")
    parser.add_argument("--db", type=str, default="data/platform.db", help="Path to SQLite database")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to YAML configuration")
    args = parser.parse_args()

    run_widget_server(db_path=args.db, config_path=args.config, port=args.port, host=args.host)
