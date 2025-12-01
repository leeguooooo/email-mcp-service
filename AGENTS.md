# Repository Guidelines

## Project Structure & Module Organization
- `src/` hosts the MCP entry (`__main__.py`, `main.py`), config (`config/paths.py`), tool handlers under `core/`, mail operations in `operations/`, services in `services/`, and schedulers in `background/`.
- `scripts/` contains automation for sync/monitoring/translation (e.g., `scripts/setup_n8n_monitoring.py`); `run.sh` boots the service with uv fallback.
- `clients/mailbox_client/` provides an optional CLI (`uv run python -m clients.mailbox_client`).
- `tests/` stores unit and regression suites with `run_tests.py`; `docs/` holds architecture and deployment guides; `n8n/` contains workflow JSON; `data/` is runtime-only (DBs, logs, attachments) and should stay local. Config samples live in `examples/` and `config_templates/`.

## Build, Test, and Development Commands
- Install dependencies: `uv sync` (uses `pyproject.toml`/`uv.lock`).
- Run the service: `./run.sh` or `uv run python -m src.main`.
- Configure accounts: `uv run python setup.py` or copy `examples/accounts.example.json` → `data/accounts.json`.
- Monitoring helpers: `uv run python scripts/setup_n8n_monitoring.py`.
- Tests: `uv run python tests/run_tests.py` or `uv run pytest tests/ --maxfail=1`.
- Lint/format/type-check: `uv run ruff check .`, `uv run black .`, `uv run mypy src`.

## Coding Style & Naming Conventions
- Python 3.11+, PEP 8, 4-space indents, and type hints on new functions.
- Modules/files use snake_case; classes PascalCase; functions/variables snake_case; constants UPPER_SNAKE.
- Prefer small, side-effect-light helpers; keep boundaries aligned with existing `operations/`, `services/`, and `core/` layers.
- Run ruff/black before pushing; docstring public APIs and MCP tools.

## Testing Guidelines
- Unit tests live under `tests/test_*.py`; rely on fixtures/mocks to avoid hitting live IMAP/SMTP.
- Add regression coverage beside the feature you touch (e.g., `test_email_lookup_fallback.py` for lookup behavior).
- Use descriptive test names showing scenario and expectation.
- Coverage targets: `uv run pytest --cov=src --cov-report=term-missing` when changing core logic; aim to exercise new branches.

## Commit & Pull Request Guidelines
- Follow the Conventional Commit style seen in history (`feat:`, `fix:`, `refactor:`); keep subjects ≤72 chars.
- Include a brief body noting user-facing changes, risks, and docs updated.
- PRs should describe context, testing performed (`uv run pytest …`), and any config migrations; attach log snippets or screenshots when relevant.
- Link issues or TODOs and request reviewers for affected areas (operations, services, scripts).

## Security & Configuration Tips
- Never commit secrets; keep `data/` contents (accounts, DBs, logs, attachments) local and gitignored.
- Use environment variables or `.env` for provider credentials; prefer config templates in `config_templates/` and examples in `examples/`.
- When debugging, scrub email addresses and tokens from shared logs.
