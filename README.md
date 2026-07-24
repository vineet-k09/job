# Autonomous Cold-Email & Job Outreach Engine

An intelligent, production-grade, resumable cold-email recruiting platform designed to automate job discovery, company research, key contact identification, custom resume tailoring, and personalized email draft creation using Gmail API & LLMs.

---

## 🌟 Key Features

- **🔄 Resumable 13-Stage Pipeline**: Built on SQLite (`data/platform.db`), allowing full crash recovery, state preservation, and safe execution restarts without redundant API calls.
- **🤖 Multi-LLM Provider Architecture**: Native support for:
  - `agy_cli` / `local_agy` (Local AGY & OpenAI-compatible endpoints)
  - `gemini` (Google Generative AI / Gemini API)
  - `anthropic` (Claude models)
  - `openai` (GPT-4 / GPT-3.5 models)
- **🔍 Research & Scraper Engine**: Dynamic web crawling powered by Playwright and fallback HTTP clients (`httpx`, `curl_cffi`) with domain rate-limiting and circuit breakers.
- **✉️ Email Verification**: Includes MX record verification, syntax validation, and SMTP check helpers to ensure zero bounce rates before generating drafts.
- **📄 Resume Tailoring via Typst**: Tailors Typst resumes (`.typ`) per target position by aligning key ATS keywords, while strictly enforcing factual integrity (no fake skills/frameworks).
- **📬 Automated Gmail Draft Creation**: Uses official Google OAuth2 / Gmail API to generate draft emails directly in your inbox for review before sending.
- **📊 Real-time Dashboard & Widget**: Embedded web server (`FastAPI` & dynamic status widget on port `18492`) for monitoring active applications, scores, and statistics.
- **📈 Data Exporter & DB Hygiene**:
  - `make export`: Exports clean outreach data to CSV and JSON formats.
  - `make clean-invalid`: Clears invalid contact emails without losing database records.

---

## 🏗️ Architecture Pipeline

```
[ Stage 0: Discovery ] ──► [ Stage 1-2: Job & Company Research ]
                                     │
[ Stage 6-7: Resume Tailoring ] ◄── [ Stage 3-5: Contact & Email Verification ]
           │
           ▼
[ Stage 8-10: Email Gen & Gmail Draft ] ──► [ Stage 11-12: Completed / Scheduled ]
```

---

## 🚀 Getting Started

### Prerequisites

- **Python**: `>= 3.11`
- **uv**: Fast Python package manager ([https://astral.sh/uv](https://astral.sh/uv))
- **Typst**: (Optional, for PDF resume generation) `typst` CLI

### Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/<your-username>/j-b.git
   cd j-b
   ```

2. **Install Dependencies**:
   ```bash
   make install
   ```
   *(or `uv sync`)*

3. **Database Initialization**:
   ```bash
   make migrate
   ```

---

## ⚙️ Configuration & Gmail Setup

### 1. Configure Settings (`config.yaml`)

`config.yaml` is **git-ignored** — it holds your personal preferences and is never committed. Copy the provided template to get started:

```bash
cp config.example.yaml config.yaml
```

Then edit `config.yaml` to fill in your identity, target roles, salary range, exclusions, and LLM provider:

```yaml
user_identity:
  name: "Jane Doe"
  email: "jane.doe@example.com"
  linkedin_url: "https://www.linkedin.com/in/jane-doe/"
  github_url: "https://github.com/jane-doe"

job_preferences:
  roles:
    - "Software Engineer"
    - "Backend Developer"
    - "AI Engineer"
  geographies:
    - "India"
    - "Remote"
  salary_range:
    min_lpa: 10.0
    max_lpa: 25.0

llm:
  provider: "agy_cli"  # Options: agy_cli, local_agy, openai, anthropic, gemini
  model: "default"
  api_key: ""
  api_url: "http://localhost:8000/v1"

gmail:
  credentials_file: "credentials.json"
  token_file: "token.json"
```

### 2. Gmail OAuth Credentials

1. Download OAuth 2.0 Client Credentials from Google Cloud Console.
2. Save the JSON file as `credentials.json` in the root directory.
3. Authenticate interactively to generate `token.json`:
   ```bash
   make auth
   ```

*(Note: `credentials.json` and `token.json` are listed in `.gitignore` to prevent credential exposure).*

---

## 🛠️ CLI & Makefile Usage

| Command | Description |
| :--- | :--- |
| `make run` | Runs the full recruiting pipeline end-to-end and launches the web widget |
| `make widget` | Launches the live dashboard & status widget on `http://localhost:18492` |
| `make target target="Company"` | Runs targeted outreach for a specific company or role |
| `make export` | Exports outreach contacts, emails, and company data to `exports/` |
| `make clean-invalid` | Scans DB and clears bad/unreachable emails without removing records |
| `make search` | Runs Stages 0–2 (Job and Company Discovery) |
| `make research` | Runs Stages 3–5 (Company and Contact Research) |
| `make tailor` | Runs Stages 6–7 (Opportunity Scoring and Resume Tailoring) |
| `make draft` | Runs Stages 8–10 (LLM Email Generation & Gmail Draft Creation) |
| `make resume` | Resumes any paused or interrupted pipeline jobs |
| `make retry` | Resets failed application states for retry |
| `make test` | Runs the test suite with `pytest` |
| `make lint` | Runs code checks using `ruff` and `mypy` |

---

## 🛡️ Security & Privacy

- All user authentication files (`credentials.json`, `token.json`), SQLite database (`data/platform.db`), generated logs (`logs/`), and exports (`exports/`) are explicitly excluded via `.gitignore`.
- **Personal config** (`config.yaml`) and your resume (`resumes/resume_*.typ`) are also git-ignored — commit only `config.example.yaml` and `resumes/resume_example.typ` to keep your preferences private.
- No API keys or OAuth secrets are hardcoded in the codebase.

---

## 📜 License

Source-Available under the [PolyForm Noncommercial License 1.0.0](LICENSE). Free for personal, educational, and non-commercial use.

