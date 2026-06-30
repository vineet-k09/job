.PHONY: install lint test run search research tailor draft retry resume ui clean format migrate help

help:
	@echo "Available commands:"
	@echo "  make install   - Install dependencies using uv"
	@echo "  make lint      - Lint code using ruff and typecheck using mypy"
	@echo "  make format    - Format code using ruff"
	@echo "  make test      - Run tests using pytest"
	@echo "  make migrate   - Initialize or migrate SQLite database"
	@echo "  make run       - Run the entire recruiting pipeline end-to-end"
	@echo "  make search    - Run Stage 0-2 (Job and Company Discovery)"
	@echo "  make research  - Run Stage 3-5 (Company and Contact Research)"
	@echo "  make tailor    - Run Stage 6-7 (Opportunity Scoring and Resume Tailoring)"
	@echo "  make draft     - Run Stage 8-10 (Email Gen and Gmail Draft Creation)"
	@echo "  make resume    - Resume any active/paused job applications"
	@echo "  make retry     - Reset failed applications and retry them"
	@echo "  make ui        - Launch the Textual terminal user interface"
	@echo "  make clean     - Clean temporary Python files and logs"

install:
	uv sync

lint:
	uv run ruff check .
	uv run mypy src/ --explicit-package-bases

format:
	uv run ruff format .

test:
	uv run pytest

migrate:
	uv run recruiting-platform init-db

run:
	uv run recruiting-platform run

search:
	uv run recruiting-platform search

research:
	uv run recruiting-platform research

tailor:
	uv run recruiting-platform tailor

draft:
	uv run recruiting-platform draft

resume:
	uv run recruiting-platform resume

retry:
	uv run recruiting-platform retry

ui:
	uv run recruiting-platform ui

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	rm -rf src/__pycache__ src/**/*.__pycache__ tests/__pycache__
	rm -f logs/platform.log
	@echo "Cleaned cache files and logs."
