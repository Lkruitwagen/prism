# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**prism** — Modelling UK energy supply by unmixing the dark side of the BMUnit.

Python 3.13 project focused on UK electricity market data, specifically around BMUnits (Balancing Mechanism Units) used in the UK's electricity balancing mechanism.

## Commands

```bash
# Create virtual environment
uv venv --python 3.13

# Install dependencies
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/path/to/test_file.py::test_name

# Lint / format
uv run ruff check .
uv run ruff format .
```

## Tooling

- **Package manager:** uv
- **Linter/formatter:** ruff (line length 100, rules: E, F, I), runs via pre-commit on commit
- **Tests:** pytest (`tests/` directory)
- **Pre-commit:** ruff-check + ruff-format hooks

## Architecture

Source code lives in `prism/`. Tests live in `tests/`.

> Update this section as the modelling architecture emerges (data ingestion, unmixing approach, output formats).

## Data Pipeline

Four data collection scripts in `scripts/`:

1. `fetch_bm_unit_catalogue.py` — BM Unit reference data → `data/bm_unit_catalogue.parquet`
2. `fetch_b1610_generation.py` — Daily generation output → `data/b1610/<date>.parquet`
3. `prepare_dukes.py` — Cleaned power plant data → `data/dukes_clean.csv`
4. `fetch_missing_bm_unit_details.py` — NETA details for BM units missing from catalogue → `data/missing_bm_unit_details.parquet`

### NETA data notes
- `data/netalist.html`: `<select>` element; each `<option value="URL">description (BM_UNIT_ID)</option>`. 11,047 units listed.
- `data/netablob.html`: example detail table; key-value rows where values may span multiple time-period columns (different `colspan`). Parser takes the last non-empty value per row (most recent).
- 1,243 B1610 units with non-zero quantity are absent from the Elexon catalogue; all 1,243 have NETA entries.

### DUKES data notes
- `data/dukes_5_11.csv` coordinates are in EPSG 27700 (British National Grid); zero values mean missing.
- `data/extra_locations.csv` provides lat/lon overrides; site names are surrounded by extra quotes — strip them before joining. Overrides apply to all matching rows (not just zero-coord ones).
- GSP geojson has `GSPs` and `GSPGroup` properties; dissolve on `GSPGroup` yields 14 regions.
- ~99 plants are unmatched to a GSP group (Northern Ireland, offshore wind) — expected.
