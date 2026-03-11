"""CLI entrypoint for fitting asset-level power curves and assignment."""

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import click
import numpy as np
import pandas as pd

from prism import fit as fit_module
from prism import solar as solar_module
from prism import wind as wind_module
from prism.bmdata import load_b1610, load_matches
from prism.met import get_solar_radiation, get_wind_speed, load_era5


@click.group()
def cli() -> None:
    """PRISM — fit asset-level power curves to BM unit generation data."""


def _detect_plant_type(tech: str | None) -> str | None:
    if tech and "wind" in tech:
        return "wind"
    if tech and ("solar" in tech or "pv" in tech):
        return "solar"
    return None


def _site_info(site_name: str, dukes: pd.DataFrame) -> tuple[float, float, str | None]:
    """Return (lat, lon, tech) for a DUKES site name."""
    plant = dukes[dukes["Site Name"] == site_name].iloc[0]
    return (
        float(plant["Latitude"]),
        float(plant["Longitude"]),
        str(plant.get("Technology", "")).lower() or None,
    )


def _fit_site(
    bm_units: list[str],
    lat: float,
    lon: float,
    plant_type: str,
    start: str,
    end: str,
    data_path: Path,
    ds,
    tau: float,
) -> dict | None:
    """Fit a power curve for one site. Returns a fit record dict or None on failure."""
    b1610 = load_b1610(data_path / "b1610", bm_units, start, end)
    if b1610.empty:
        click.echo(f"  No B1610 data for {bm_units} — skipping.", err=True)
        return None

    met_series = (
        get_wind_speed(ds, lat, lon) if plant_type == "wind" else get_solar_radiation(ds, lat, lon)
    )

    common_idx = b1610.index.intersection(met_series.index)
    if len(common_idx) == 0:
        click.echo("  No overlapping timestamps — skipping.", err=True)
        return None

    obs = b1610.loc[common_idx, "quantity"].values.astype(float)
    met = met_series.loc[common_idx].values.astype(float)

    capacity_est = float(np.nanpercentile(obs[obs > 0], 99)) if np.any(obs > 0) else 100.0

    if plant_type == "wind":
        init_params = wind_module.default_params(capacity_mw=capacity_est)
        power_fn = wind_module.wind_power
        pnames = wind_module.param_names()
    else:
        init_params = solar_module.default_params(capacity_mw=capacity_est)
        power_fn = solar_module.solar_power
        pnames = solar_module.param_names()

    result = fit_module.fit(power_fn, init_params, met, obs, tau=tau)

    fit_params = {name: float(np.exp(val)) for name, val in zip(pnames, result.x, strict=False)}
    fit_params["plant_type"] = plant_type
    fit_params["converged"] = bool(result.success)
    fit_params["loss"] = float(result.fun)

    click.echo(f"  converged={result.success}  loss={result.fun:.4f}")
    for name, val in zip(pnames, result.x, strict=False):
        click.echo(f"    {name:30s} = {np.exp(val):.4g}")

    return {"lat": lat, "lon": lon, "fit_params": fit_params}


def _merge_records(existing: list[dict], new_records: list[dict]) -> list[dict]:
    """Replace existing records whose bm_units overlap with new ones, then append."""
    new_unit_sets = [set(r["bm_units"]) for r in new_records]
    kept = [r for r in existing if set(r["bm_units"]) not in new_unit_sets]
    return kept + new_records


@cli.command()
@click.option(
    "--bm-unit",
    "bm_unit_spec",
    required=True,
    help=(
        "BM unit ID(s) to fit. Options: a single ID (e.g. T_HOWAO-1), "
        "a comma-separated list of IDs (each resolved to its site), "
        "or a keyword: 'all', 'all-wind', 'all-solar'."
    ),
)
@click.option("--start", required=True, help="Start date (YYYY-MM-DD, inclusive)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD, inclusive)")
@click.option(
    "--type",
    "plant_type",
    type=click.Choice(["wind", "solar"]),
    default=None,
    help="Plant type override (auto-detected from DUKES if omitted)",
)
@click.option(
    "--all-units/--single-unit",
    default=True,
    show_default=True,
    help="Sum all BM units at the same site (default) or fit the specified unit only",
)
@click.option("--data-dir", default="data", show_default=True, help="Root data directory")
@click.option(
    "--tau",
    default=0.5,
    show_default=True,
    help="Quantile for asymmetric loss (0.5 = median)",
)
@click.option(
    "--output",
    default="data/fits.json",
    show_default=True,
    help="Output JSON file (merged with existing records)",
)
def fit(
    bm_unit_spec: str,
    start: str,
    end: str,
    plant_type: str | None,
    all_units: bool,
    data_dir: str,
    tau: float,
    output: str,
) -> None:
    """Fit wind or solar power curves and save parameters to JSON."""
    data_path = Path(data_dir)
    matches = load_matches(data_path / "matches.csv")
    dukes = pd.read_csv(data_path / "dukes_clean.csv")

    # --- Resolve which sites to fit ---
    _KEYWORDS = {"all", "all-wind", "all-solar"}
    sites: list[dict] = []  # each entry: {bm_units, lat, lon, plant_type}

    if bm_unit_spec in _KEYWORDS:
        type_filter = None
        if bm_unit_spec == "all-wind":
            type_filter = "wind"
        elif bm_unit_spec == "all-solar":
            type_filter = "solar"

        for site_name, group in matches.groupby("dukes_site_name"):
            try:
                lat, lon, tech = _site_info(site_name, dukes)
            except IndexError:
                click.echo(
                    f"Warning: '{site_name}' not found in dukes_clean.csv — skipping.", err=True
                )
                continue

            detected = _detect_plant_type(tech)
            effective_type = plant_type or detected

            if effective_type is None:
                click.echo(
                    f"  Skipping '{site_name}': cannot detect plant type (tech='{tech}').", err=True
                )
                continue

            if type_filter and effective_type != type_filter:
                continue

            sites.append(
                {
                    "bm_units": group["bm_unit_id"].tolist(),
                    "lat": lat,
                    "lon": lon,
                    "plant_type": effective_type,
                    "site_name": site_name,
                }
            )
    else:
        # Comma-separated individual BM unit IDs
        requested_ids = [u.strip() for u in bm_unit_spec.split(",")]
        for unit_id in requested_ids:
            row = matches[matches["bm_unit_id"] == unit_id]
            if row.empty:
                click.echo(
                    f"Warning: {unit_id} not found in matches.csv — using UK centre coords.",
                    err=True,
                )
                lat, lon, tech, site_name = 54.0, -2.0, None, None
            else:
                site_name = row.iloc[0]["dukes_site_name"]
                lat, lon, tech = _site_info(site_name, dukes)

            detected = _detect_plant_type(tech)
            effective_type = plant_type or detected
            if effective_type is None:
                raise click.UsageError(
                    f"Cannot auto-detect plant type for {unit_id} (tech='{tech}'). Use --type."
                )

            if all_units and site_name is not None:
                bm_units = matches[matches["dukes_site_name"] == site_name]["bm_unit_id"].tolist()
            else:
                bm_units = [unit_id]

            sites.append(
                {
                    "bm_units": bm_units,
                    "lat": lat,
                    "lon": lon,
                    "plant_type": effective_type,
                    "site_name": site_name,
                }
            )

    if not sites:
        raise click.ClickException("No sites resolved to fit.")

    click.echo(f"Fitting {len(sites)} site(s)  |  tau={tau}")

    # --- Load ERA5 once ---
    era5_path = data_path / "era5_uk_2026_jan_feb.nc"
    ds = load_era5(era5_path)

    # --- Fit each site ---
    output_records: list[dict] = []
    for site in sites:
        click.echo(
            f"\n[{site['site_name'] or site['bm_units']}]  type={site['plant_type']}  "
            f"units={site['bm_units']}  ({site['lat']:.4f}, {site['lon']:.4f})"
        )
        fit_record = _fit_site(
            bm_units=site["bm_units"],
            lat=site["lat"],
            lon=site["lon"],
            plant_type=site["plant_type"],
            start=start,
            end=end,
            data_path=data_path,
            ds=ds,
            tau=tau,
        )
        if fit_record is not None:
            output_records.append({"bm_units": site["bm_units"], "fits": [fit_record]})

    # --- Merge with existing JSON and save ---
    output_path = Path(output)
    existing: list[dict] = []
    if output_path.exists():
        existing = json.loads(output_path.read_text())

    merged = _merge_records(existing, output_records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(merged, indent=2))

    click.echo(
        f"\nSaved {len(output_records)} new fit(s) to {output_path}  ({len(merged)} total records)"
    )


@cli.command()
@click.option("--start", required=True, help="Start date (YYYY-MM-DD, inclusive)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD, inclusive)")
@click.option(
    "--gsp-group",
    "gsp_group",
    default="all",
    show_default=True,
    help="GSP group to solve (e.g. '_A') or 'all' to run every group in sequence.",
)
@click.option("--data-dir", default="data", show_default=True, help="Root data directory")
@click.option(
    "--output",
    default="data/assignment.json",
    show_default=True,
    help="Output JSON file for the asset-to-supplier assignment",
)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable verbose logging")
def assign(
    start: str,
    end: str,
    gsp_group: str,
    data_dir: str,
    output: str,
    verbose: bool,
) -> None:
    """Assign unmatched wind/solar DUKES plants to supplier BM units via MILP.

    Solves one mixed-integer linear programme per GSP group, minimising the
    total unexplained supplier-unit generation.  Results are persisted as JSON.
    """
    from prism.assignment import run_assignment

    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s %(message)s")

    click.echo(f"Running assignment  start={start}  end={end}  gsp_group={gsp_group}")
    run_assignment(
        data_path=Path(data_dir),
        start=start,
        end=end,
        gsp_group=gsp_group,
        output_path=Path(output),
    )
    click.echo(f"Done — results written to {output}")


@cli.command()
@click.option(
    "--date",
    "date_str",
    default=None,
    help="Date to infer (YYYY-MM-DD). Defaults to today minus --lag days.",
)
@click.option(
    "--lag",
    default=10,
    show_default=True,
    help="Days lag from today when --date is not specified (ERA5 availability buffer).",
)
@click.option("--data-dir", default="data", show_default=True, help="Root data directory")
@click.option(
    "--fits-wind",
    default="data/fits-wind.json",
    show_default=True,
    help="Wind fits JSON",
)
@click.option(
    "--fits-solar",
    default="data/fits-solar.json",
    show_default=True,
    help="Solar fits JSON",
)
@click.option(
    "--assignment",
    default="data/assignment.json",
    show_default=True,
    help="Assignment JSON (unmatched plants)",
)
@click.option(
    "--output-dir",
    default="data",
    show_default=True,
    help="Directory to write inference_<date>.json",
)
@click.option(
    "--bucket",
    default=None,
    envvar="GCS_BUCKET",
    help="GCS bucket name to upload result (reads GCS_BUCKET env var if not set).",
)
def infer(
    date_str: str | None,
    lag: int,
    data_dir: str,
    fits_wind: str,
    fits_solar: str,
    assignment: str,
    output_dir: str,
    bucket: str | None,
) -> None:
    """Estimate plant-level generation for a given day and store as JSON blob."""
    from prism.inference import run_inference

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if date_str is None:
        date_str = (date.today() - timedelta(days=lag)).isoformat()

    click.echo(f"Running inference for {date_str}")

    data_path = Path(data_dir)
    result = run_inference(
        date_str=date_str,
        data_path=data_path,
        fits_wind_path=Path(fits_wind),
        fits_solar_path=Path(fits_solar),
        assignment_path=Path(assignment),
    )

    # Save locally
    out_path = Path(output_dir) / f"inference_{date_str}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    click.echo(f"Saved to {out_path}")

    # Upload to GCS if bucket specified
    if bucket:
        import gcsfs

        dest = f"{bucket}/inference_{date_str}.json"
        click.echo(f"Uploading to gs://{dest} ...")
        fs = gcsfs.GCSFileSystem()
        with fs.open(dest, "w") as fp:
            json.dump(result, fp)
        click.echo("Upload complete.")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
