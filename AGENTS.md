# Repository Guidelines

## Project Structure

This repository is a small Python command-line scraper for J.League player statistics. `main.py` handles the CLI and interactive flow, `scraper.py` fetches and parses official site data, and `output.py` writes CSV files. `README.md` documents usage and supported seasons. `requirements.txt` lists runtime dependencies. There is no dedicated test or asset directory; generated CSVs belong in output directories and should not be committed unless specifically needed as fixtures.

## Development Commands

- `python -m venv .venv` creates an isolated environment.
- `python -m pip install -r requirements.txt` installs dependencies.
- `python main.py` starts the interactive wizard.
- `python main.py --season 2026 --category j1 --team shimizu` runs a sample scrape.
- `python main.py --list-teams --season 2025 --category j1` lists valid team identifiers.

Scraping requires network access to the J.League site and may take several minutes when requesting all teams or stats.

## Coding Style

Use Python 3.12 or newer, four spaces for indentation, and descriptive `snake_case` names for functions and variables. Keep CLI validation and user-facing messages in `main.py`, site retrieval/parsing in `scraper.py`, and CSV formatting/writing in `output.py`. Follow nearby code patterns and keep CSV headers and output filenames consistent with the Japanese labels documented in `README.md`. No formatter or linter is configured.

## Testing

Run the automated suite from the repository root:

- `python -m pytest` runs all tests in `tests/`.
- `pip install -r requirements-dev.txt` installs pytest alongside runtime deps.

Tests must not touch the network. HTTP access is stubbed by monkeypatching `scraper._request_with_retry` and `scraper._get_session`; parser tests use trimmed real-page HTML under `tests/fixtures/`. Add new parser/CSV cases when changing parsing or output behavior, and keep each test focused. When a change touches retrieval or CSV behavior beyond the suite, still do a narrow manual check (`--team <one team> --stats <a few>`) and inspect the generated CSV and error log. Avoid unnecessary broad scrapes; they make many network requests.

## Commits and Pull Requests

Recent commit subjects are short and action-oriented, with both English and Japanese used (for example, `Remove stat source columns from CSV`). Keep each commit focused and describe the user-visible effect. Pull requests should explain the change and motivation, list the commands or checks performed, and include a small before/after example for changes to CLI output or CSV columns. Link related issues when applicable.

## Configuration and Data

Do not commit credentials, local environments, or generated output. Respect the scraper's request delays and retry behavior when changing network access. The official site's HTML can change, so document any assumptions about page structure and update `README.md` when supported arguments or output formats change.
