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

### Power curve fitting notes (TASK 05)
- `prism/wind.py` — **`wind_power`**: 5-param physical model (capacity, v_cutin, v_rated, k, v_cutout); `jnp.clip(norm, 1e-4, 1.0)` to avoid `0^k` NaN gradients when k<1; smooth cutin/cutout via `jax.nn.sigmoid` (NOT custom jnp.where sigmoid — NaN gradients for large inputs); **`wind_power_weibull`** kept for comparison (lacks plateau, fits poorly above rated speed)
- `prism/solar.py` — Linear P = scale × G (W/m²); `solar_radiation` is SSRD from ERA5 in W/m² (not accumulated J/m²)
- `prism/fit.py` — `scipy.optimize.minimize` (L-BFGS-B) + `jax.value_and_grad`; quantile loss default **tau=0.5** (median regression — fits through bulk of data, unbiased under symmetric ERA5 noise); use tau>0.5 only for explicit upper-envelope fitting
- `prism/met.py` — ERA5 load + nearest-point sampling for wind speed and solar radiation
- `prism/bmdata.py` — B1610 loader; datetime = settlementDate + (period-1)*30min (period-start convention)
- `prism/cli.py` — `prism fit` command; auto-detects wind/solar from DUKES Technology field
- `notebooks/05_fitting_power_curves.ipynb` — end-to-end example: Hornsea 01, Jan-Feb 2026
- Hornsea 01 fitted capacity ~590 MW (3 BM units: T_HOWAO-1/2/3), scale λ≈7.4 m/s, shape k≈2.4–3.0; 33% of periods show curtailment
- ERA5 SSRD units are W/m² (instantaneous), not accumulated J/m²

### Assignment notes (TASK 06)
- `prism/assignment.py` — MILP assignment of unmatched wind/solar DUKES plants to supplier BM units
- Supplier BM units have `bmUnitType == 'S'` in catalogue; 289 units across 14 GSP groups
- MILP formulation: binary x[asset, supplier]; maximise assigned generation; constraints: each asset to ≤1 supplier, don't over-assign supplier capacity
- Uses linopy + HiGHs (highspy package); `m.solve('highs', io_api='direct')` returns a tuple; check `m.termination_condition == 'optimal'`
- `InstalledCapacity (MW)` in DUKES has `\t` tab prefix — strip whitespace before parsing
- 951 unmatched wind/solar assets across 14 GSP groups; solved per-group independently
- `prism/cli.py` — `prism assign` command; `--gsp-group` option accepts a single GSP ID or 'all'
- Output: `data/assignment.json` — dict {dukes_index_str: {bm_unit_id, site_name, lat, lon, tech, capacity_mw, gsp_group, estimated_generation}}
- Dependencies added: `linopy>=0.6.5`, `highspy>=1.13.1`

### ERA5 weather data notes
- Source: `gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3` (public, anonymous access via `token="anon"`)
- Variables: `100m_u/v_component_of_wind`, `2m_temperature`, `surface_solar_radiation_downwards`, `total_precipitation`, plus derived `100m_wind_speed`
- Task spec had typo "total_preciptiation" — correct name is `total_precipitation`
- ERA5 latitude dimension is **descending** — use `slice(LAT_MAX, LAT_MIN)` to select correctly
- Longitude is native [0, 360]; roll to [-180, 180] before filtering
- Interpolation to half-hourly requires `scipy` (xarray uses `scipy.interpolate.interp1d`)
- Output shape: (2831 timesteps × 41 lat × 49 lon), ~260 MB as NetCDF

### Orchestration notes (TASK 07)
- `prism/fetch.py` — `fetch_b1610_day(date, output_dir)` and `fetch_era5_day(date)` for single-day fetches
- `prism/inference.py` — `run_inference(date_str, data_path, fits_wind_path, fits_solar_path, assignment_path)` → JSON-serialisable dict
- `prism/cli.py` — `prism infer` command; `--date` (defaults to today - `--lag` days, default lag=10); `--bucket` reads `GCS_BUCKET` env var
- Output: `data/inference_<YYYY-MM-DD>.json` — `{date, bm_unit_quantities: {unit_id: {period: MW}}, plant_generation: [...]}`
- `plant_generation` entries have `source: "matched"` (uses fitted params from fits-wind/solar.json) or `source: "unmatched"` (uses default params scaled to DUKES capacity)
- `data/fits-wind.json` and `data/fits-solar.json` are checked in so they're available in the GitHub runner
- `.github/workflows/daily_inference.yml` — cron `0 2 * * *`; uses `google-github-actions/auth@v2` with `GCP_SA_KEY` secret; `GCS_BUCKET` from GitHub vars
- `gcsfs` (already a dep) handles GCS upload via Application Default Credentials set by the auth action
- ERA5 is fetched fresh each day (one day = small, fast); 10-day default lag ensures archive availability
- For DatetimeIndex filtering by date: `series[series.index.date == d]` (not `.iloc` with boolean array)
