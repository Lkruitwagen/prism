# prism
Modelling UK energy supply by unmixing the dark side of the BMUnit.

## Developer Setup

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
# Create virtual environment
uv venv --python 3.13

# Install dependencies (including dev extras)
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install
```

### Running tests

```bash
uv run pytest
```

### Linting

```bash
uv run ruff check .
uv run ruff format .
```

Pre-commit runs ruff automatically on every commit.

## Scripts

Scripts live in `scripts/` and are run with `uv run python scripts/<script_name>.py`.

- **`fetch_bm_unit_catalogue.py`** — Fetches the complete BM Unit catalogue from the Elexon BMRS API and saves it as `data/bm_unit_catalogue.parquet`.
- **`fetch_b1610_generation.py`** — Fetches B1610 actual generation output per BM unit for a date range, saving one parquet file per day under `data/b1610/`. Usage: `uv run python scripts/fetch_b1610_generation.py --start YYYY-MM-DD --end YYYY-MM-DD`.
- **`prepare_dukes.py`** — Reprojects DUKES power plant coordinates from EPSG 27700 to EPSG 4326, backfills missing/incorrect coordinates from `data/extra_locations.csv`, dissolves GSP region polygons to `GSPGroup`, and spatially joins GSP group onto the plant data. Output saved as `data/dukes_clean.csv`.

## Data Sources

- [Elexon BMRS API](https://data.elexon.co.uk/bmrs/api/v1/reference/bmunits/all) — BM Unit reference catalogue.
- [Elexon BMRS B1610 stream](https://data.elexon.co.uk/bmrs/api/v1/datasets/B1610/stream) — Actual generation output per generating unit.
- [DUKES 5.11](https://www.gov.uk/government/statistics/digest-of-uk-energy-statistics-dukes) — UK power plant data from the Digest of UK Energy Statistics (table 5.11), including technology, fuel type, capacity, and grid connection.
- [NESO GSP Regions](https://data.nationalgrideso.com/) — Grid Supply Point (GSP) region boundaries in GeoJSON format (EPSG 4326), used to assign plants to GSP groups.
