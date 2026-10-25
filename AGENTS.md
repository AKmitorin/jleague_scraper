# Repository Guidelines

## Project Structure

This repository is a small Python command-line scraper for J.League player statistics. `main.py` handles the CLI and interactive flow; `scraper.py` orchestrates one team's collection; `player_stats.py` fetches and parses player lists, rankings, and player pages; `team_names.py` resolves club slugs to names; `http_client.py` performs HTTP requests with retries; `stat_definitions.py` holds the stat codes, position rules, and season constants; and `output.py` writes CSV files. `README.md` documents usage and supported seasons. `pyproject.toml` declares the runtime dependencies and the `dev` dependency group (pytest), and `uv.lock` pins the resolved versions. Tests live in `tests/` (with page excerpts in `tests/fixtures/`); generated CSVs belong in output directories and should not be committed.

## Development Commands

- `uv sync` creates `.venv` and installs all dependencies (including the `dev` group).
- `uv add <package>` (or `uv add --dev <package>`) adds a dependency and updates `uv.lock`; commit the lockfile with the change.
- `uv run main.py` starts the interactive wizard.
- `uv run main.py --season 2026 --category j1 --team shimizu` runs a sample scrape.
- `uv run main.py --list-teams --season 2025 --category j1` lists valid team identifiers.

Scraping requires network access to the J.League site and may take several minutes when requesting all teams or stats.

## Coding Style

Use Python 3.12 or newer, four spaces for indentation, and descriptive `snake_case` names for functions and variables. Keep CLI validation and user-facing messages in `main.py`, HTTP in `http_client.py`, site retrieval/parsing in `player_stats.py`/`team_names.py`, stat definitions in `stat_definitions.py`, collection orchestration in `scraper.py`, and CSV formatting/writing in `output.py`. Follow nearby code patterns and keep CSV headers and output filenames consistent with the Japanese labels documented in `README.md`. No formatter or linter is configured.

## Testing

Run the automated suite from the repository root:

- `uv run pytest` runs all tests in `tests/`.
- `uv sync` installs pytest through the `dev` dependency group.

Tests must not touch the network. HTTP access is stubbed by monkeypatching `http_client.request_with_retry` / `http_client.get_session` (or the `request_with_retry`/`get_session` imported into the module under test); parser tests use trimmed real-page HTML under `tests/fixtures/`. Add new parser/CSV cases when changing parsing or output behavior, and keep each test focused. When a change touches retrieval or CSV behavior beyond the suite, still do a narrow manual check (`--team <one team> --stats <a few>`) and inspect the generated CSV and error log. Avoid unnecessary broad scrapes; they make many network requests.

## Commits and Pull Requests

Recent commit subjects are short and action-oriented, with both English and Japanese used (for example, `Remove stat source columns from CSV`). Keep each commit focused and describe the user-visible effect. Pull requests should explain the change and motivation, list the commands or checks performed, and include a small before/after example for changes to CLI output or CSV columns. Link related issues when applicable.

## Configuration and Data

Do not commit credentials, local environments, or generated output. Respect the scraper's request delays and retry behavior when changing network access. The official site's HTML can change, so document any assumptions about page structure and update `README.md` when supported arguments or output formats change.
