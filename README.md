# Cold-Email Recruiting Platform

A production-grade, extensible, resumable cold-email recruiting platform designed to automate and streamline the job search, research, and outreach process.

## Architecture

This platform is structured as a pipeline of stages from Stage 0 (Discovery) to Stage 12 (Completed). It utilizes SQLite to maintain state, ensuring resumability in the event of crashes or interruptions.

## Requirements

- Python >= 3.11
- `uv` (Fast Python Package Installer and Resolver)

## Getting Started

1. Set up dependencies:
   ```bash
   make install
   ```
2. Configure settings:
   Create/modify `config.yaml`.
3. Run the CLI:
   ```bash
   uv run recruiting-platform --help
   ```
4. Run the Textual UI:
   ```bash
   make ui
   ```
