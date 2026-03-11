![fun prism logo](ui/im.png)

# PRISM
Modelling UK energy supply by unmixing the dark side of VPP BM Units.

View UI [here](https://head.prism-kzi.pages.dev).

## Problem Statement

One of the largest costs for energy market participants is imbalance costs; one for the largest opportunities for traders and flexibility providers is providing balancing services or trading the system imbalance price.

Accurately forecasting the system imbalance price requires forecasting system supply and demand.
Energy system supply is increasingly driven by renewable energy availability - the sun and wind - and the UK has large amounts of both.
_The challenge this work addresses is getting detailed, asset-level data that you can use to fit power curves for wind and solar assets_.

This project will develop a model of asset-level solar and wind energy supply using real physical generation data.
The problem this work addresses are two-fold:
  - first, where asset-level physical generation data is available, we will fit power curves for wind or solar generation
  - second, where individual assets are agglomerated to virtual power plants, we will unmix these signals back into asset-level timeseries.

The result is a generation model for every solar or wind asset in the UK mapped back to reported balancing mechanism unit physical generation data.

## Approach

The approach is as follows:
- Obtain data on UK electricity plants, including technology type and lat/lon location.
- Obtain balancing mechanism physical generation data for all `bm_units`.
- Match `bm_units` to electricity plants. 
- Obtain historic weather data: direct solar irradiance and windspeed.
- For BM units that match at the asset level, sample timeseries of input weather data and parameterise power curve model:
  - for solar PV units, just model a static efficiency factor on top of nominal capacity.
  - for wind units, fit a power-law curve, with sigmoidal cut-in and cut-out activations
- For BM units that represent agglomerations of embedded plants, match remaining plants using a binary assignment problem, a problem formulation using a mixed-integer linear programme.
- Set up orchestration so that we can run our fit models every day (with a lag to allow weather and balancing data to propagate).
- Build a lightweight UI to visualise the model and residual drift.

## Data Sources

- UK electricity plants: [DUKES 5.11](https://www.gov.uk/government/collections/digest-of-uk-energy-statistics-dukes)
- Actual BM Unit Generation Output: [BMRS B1610](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/B1610/stream)
- BM Unit details: [BMRS Reference BM Units](https://bmrs.elexon.co.uk/api-documentation/endpoint/reference/bmunits/all)
- Missing BM Unit details: [NETA Reports](https://www.netareports.com/data/elexon.jsp)
- Historic weather data: [ERA5 Reanalysis](https://console.cloud.google.com/storage/browser/gcp-public-data-arco-era5;tab=objects?pageState=(%22StorageObjectListTable%22:(%22f%22:%22%255B%255D%22))&prefix=&forceOnObjectsSortingFiltering=false)
- Grid Supply Point (GSP) region boundaries: [NESO](https://www.neso.energy/data-portal/gis-boundaries-gb-grid-supply-points), simplified with [MapShaper](https://mapshaper.org/).


## Useage

PRISM is shipped with a cli that allows you to run the main fitting and assigning functions.

    prism --help

You can also find individual scripts in [scripts](scripts/) to help setup and download data.

### Fit asset-level BM Units

To fit asset-level data to weather data, use `prism fit`:

```
Usage: prism fit [OPTIONS]

  Fit wind or solar power curves and save parameters to JSON.

Options:
  --bm-unit TEXT               BM unit ID(s) to fit. Options: a single ID
                               (e.g. T_HOWAO-1), a comma-separated list of IDs
                               (each resolved to its site), or a keyword:
                               'all', 'all-wind', 'all-solar'.  [required]
  --start TEXT                 Start date (YYYY-MM-DD, inclusive)  [required]
  --end TEXT                   End date (YYYY-MM-DD, inclusive)  [required]
  --type [wind|solar]          Plant type override (auto-detected from DUKES
                               if omitted)
  --all-units / --single-unit  Sum all BM units at the same site (default) or
                               fit the specified unit only  [default: all-
                               units]
  --data-dir TEXT              Root data directory  [default: data]
  --tau FLOAT                  Quantile for asymmetric loss (0.5 = median)
                               [default: 0.5]
  --output TEXT                Output JSON file (merged with existing records)
                               [default: data/fits.json]
  --help                       Show this message and exit.
```

For example:

    prism fit --bm-unit T_HOWAO-1 --start 2026-01-01 --end 2026-02-28

### Assign assets to BM Units

To run the MILP that assigns unmatched assets to BM Units, run `prism assign`.

```
Usage: prism assign [OPTIONS]

  Assign unmatched wind/solar DUKES plants to supplier BM units via MILP.

  Solves one mixed-integer linear programme per GSP group, minimising the
  total unexplained supplier-unit generation.  Results are persisted as JSON.

Options:
  --start TEXT      Start date (YYYY-MM-DD, inclusive)  [required]
  --end TEXT        End date (YYYY-MM-DD, inclusive)  [required]
  --gsp-group TEXT  GSP group to solve (e.g. '_A') or 'all' to run every group
                    in sequence.  [default: all]
  --data-dir TEXT   Root data directory  [default: data]
  --output TEXT     Output JSON file for the asset-to-supplier assignment
                    [default: data/assignment.json]
  -v, --verbose     Enable verbose logging
  --help            Show this message and exit.
```

For example:

    prism assign --start 2026-01-01 --end 2026-01-08 --gsp-group _A

## AI Approach

This codebase has been developed with the extensive support of Claude Code.
Very few human interventions have been made in the actual code itself.
The intention with this was to get as far as possible in a short time, demonstrating some concepts
and potentially showing some new insights into how energy supply can be modelled.

This repo uses task cards in [TASKS](TASKS) to help the coding assistant walk through the development steps.
In general, enough details are given on these cards that agent-supported development isn't necessary.
The overall structure of this repo, the python modules, and much of the detailed data manipulation were documented in detail,
giving the coding assistant plenty of guidance.
Where the coding assistant needed further detail, this was provided.

Even with this detailed level of intervention, the coding assistant still made several basic and important mistakes; 
I'm skeptical that the work in this repo could have been achieved with higher-abstracted instructions.
The code 'smells' very machine-generated and rushed - difficult to read/follow; missing abstractions; and functional rather than object-oriented.
There's also no testing, despite an optimistic subdirectory created at the beginning!

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