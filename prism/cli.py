"""CLI entrypoint for fitting asset-level power curves."""

import json
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


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
