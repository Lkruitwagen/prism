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

Six scripts in `scripts/`:

1. `fetch_bm_unit_catalogue.py` — BM Unit reference data → `data/bm_unit_catalogue.parquet`
2. `fetch_b1610_generation.py` — Daily generation output → `data/b1610/<date>.parquet`
3. `prepare_dukes.py` — Cleaned power plant data → `data/dukes_clean.csv`
4. `fetch_missing_bm_unit_details.py` — NETA details for BM units missing from catalogue → `data/missing_bm_unit_details.parquet`
5. `match_dukes_to_bm_units.py` — Interactive CLI matching DUKES plants to BM units → `data/matches.json`
6. `fetch_era5_uk.py` — ERA5 weather cube for UK, Jan-Feb 2026 → `data/era5_uk_2026_jan_feb.nc`

### NETA data notes
- `data/netalist.html`: `<select>` element; each `<option value="URL">description (BM_UNIT_ID)</option>`. 11,047 units listed.
- `data/netablob.html`: example detail table; key-value rows where values may span multiple time-period columns (different `colspan`). Parser takes the last non-empty value per row (most recent).
- 1,243 B1610 units with non-zero quantity are absent from the Elexon catalogue; all 1,243 have NETA entries.

### Matching notes
- `data/matches.json` — output of `match_dukes_to_bm_units.py`; keys are DUKES row index (sorted by capacity desc), values are `{site_name, bm_units: [...elexonBmUnit...]}`.
- Matching uses `rapidfuzz.partial_ratio` on a composite string (bmUnitName + leadPartyName + elexonBmUnit + nationalGridBmUnit) vs DUKES site name + company.
- b1610 stats (max/min observed quantity) computed via `pyarrow.dataset` (efficient columnar scan, no full load needed).
- `ruff` must be installed as a dev dep (`uv add ruff --dev`) — it is not in the default `uv sync --extra dev` path without this.

### DUKES data notes
- `data/dukes_5_11.csv` coordinates are in EPSG 27700 (British National Grid); zero values mean missing.
- `data/extra_locations.csv` provides lat/lon overrides; site names are surrounded by extra quotes — strip them before joining. Overrides apply to all matching rows (not just zero-coord ones).
- GSP geojson has `GSPs` and `GSPGroup` properties; dissolve on `GSPGroup` yields 14 regions.
- ~99 plants are unmatched to a GSP group (Northern Ireland, offshore wind) — expected.

### Notebook exploration notes (TASK 04)
- `notebooks/04_explore_bm_units.ipynb` — explores DUKES/BM unit matches with three plots
- DUKES must be sorted by `parse_capacity` descending (strip whitespace from capacity string) before using matches.json indices — the matching script uses this sort order
- B1610 quantity is in MW (average over 30-min period); multiply by 0.5 to get MWh per period
- 26 DUKES plants matched → 81 BM units; matched series include bioenergy, CCGT, nuclear, pumped-hydro, wind
- Negative B1610 quantities (demand, pumping, interconnector import) stacked below x-axis in stacked area plot
- `nbconvert` output path: pass just the filename (not full path) when notebook is inside a subdir, to avoid double-prefixing; executed notebook replaces source
- `nbconvert`, `nbformat`, `nbclient`, `ipykernel` added as deps for notebook execution

### ERA5 weather data notes
- Source: `gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3` (public, anonymous access via `token="anon"`)
- Variables: `100m_u/v_component_of_wind`, `2m_temperature`, `surface_solar_radiation_downwards`, `total_precipitation`, plus derived `100m_wind_speed`
- Task spec had typo "total_preciptiation" — correct name is `total_precipitation`
- ERA5 latitude dimension is **descending** — use `slice(LAT_MAX, LAT_MIN)` to select correctly
- Longitude is native [0, 360]; roll to [-180, 180] before filtering
- Interpolation to half-hourly requires `scipy` (xarray uses `scipy.interpolate.interp1d`)
- Output shape: (2831 timesteps × 41 lat × 49 lon), ~260 MB as NetCDF
