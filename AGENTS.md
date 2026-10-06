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

No automated test suite is currently present. For changes to parsing or CSV behavior, perform a focused manual check with a narrow team/stat selection, then inspect the generated CSV and error log. Avoid unnecessary broad scrapes; they make many network requests. If adding tests, use `pytest`, name files `test_*.py`, and keep network-dependent checks opt-in or mocked.

## Commits and Pull Requests

Recent commit subjects are short and action-oriented, with both English and Japanese used (for example, `Remove stat source columns from CSV`). Keep each commit focused and describe the user-visible effect. Pull requests should explain the change and motivation, list the commands or checks performed, and include a small before/after example for changes to CLI output or CSV columns. Link related issues when applicable.

## Configuration and Data

Do not commit credentials, local environments, or generated output. Respect the scraper's request delays and retry behavior when changing network access. The official site's HTML can change, so document any assumptions about page structure and update `README.md` when supported arguments or output formats change.
