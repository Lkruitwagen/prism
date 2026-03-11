"""MILP assignment of unmatched DUKES assets to supplier BM units.

For each GSP group, solves a mixed-integer linear programme that assigns
unmatched wind/solar plants to supplier-type BM units so as to minimise the
total absolute residual between assigned and observed supplier generation,
summed over all time periods.

Formulation (per GSP group)
---------------------------
Variables:
    x[i, j] ∈ {0, 1}     —  1 if asset i is assigned to supplier j
    r[j, t] ≥ 0           —  absolute residual for supplier j at time t

Constraints:
    Σ_j x[i, j] ≤ 1                                     ∀ i
    r[j, t] ≥   Σ_i x[i, j] * G[i, t] − B[j, t]        ∀ j, t
    r[j, t] + Σ_i x[i, j] * G[i, t] ≥ B[j, t]          ∀ j, t

Objective:
    minimise Σ_j Σ_t r[j, t]

where
    G[i, t]  =  estimated generation of asset i at half-hour t (MW)
    B[j, t]  =  observed positive generation of supplier j at half-hour t (MW)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import linopy
import numpy as np
import pandas as pd
import xarray as xr

from prism.met import get_solar_radiation, get_wind_speed
from prism.solar import default_params as solar_default_params
from prism.solar import solar_power
from prism.wind import default_params as wind_default_params
from prism.wind import wind_power

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generation estimation
# ---------------------------------------------------------------------------


def _parse_capacity(raw: str | float) -> float:
    """Strip whitespace/tabs and return float capacity in MW (NaN on failure)."""
    try:
        return float(str(raw).strip())
    except ValueError:
        return float("nan")


def estimate_generation_timeseries(
    lat: float,
    lon: float,
    capacity_mw: float,
    tech: str,
    era5_ds,
    start: str,
    end: str,
) -> pd.Series:
    """Return estimated generation timeseries (MW) over [start, end].

    Uses default power-curve parameters and the nearest ERA5 grid point.
    Returns an empty Series on failure.
    """
    try:
        if tech == "wind":
            met_series = get_wind_speed(era5_ds, lat, lon)
            params = wind_default_params(capacity_mw=capacity_mw)
            power_fn = wind_power
        else:  # solar
            met_series = get_solar_radiation(era5_ds, lat, lon)
            params = solar_default_params(capacity_mw=capacity_mw)
            power_fn = solar_power

        met_series = met_series.loc[start:end]
        if met_series.empty:
            return pd.Series(dtype=float)

        power_vals = np.array(power_fn(np.array(params), met_series.values.astype(float)))
        return pd.Series(power_vals, index=met_series.index)

    except Exception as exc:
        logger.warning("estimate_generation_timeseries failed for (%s, %s): %s", lat, lon, exc)
        return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def load_unmatched_assets(
    dukes_path: str | Path,
    matches_path: str | Path,
    era5_ds,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, xr.DataArray]:
    """Build metadata DataFrame and generation DataArray for unmatched wind/solar assets.

    Returns:
        meta_df:  columns [asset_id, site_name, lat, lon, tech, capacity_mw, gsp_group]
        G:        xr.DataArray with dims [asset, time], generation in MW per half-hour
    """
    dukes = pd.read_csv(dukes_path)
    matches = pd.read_csv(matches_path, index_col=0)
    matched_sites = set(matches["dukes_site_name"].unique())

    unmatched = dukes[~dukes["Site Name"].isin(matched_sites)].copy()
    unmatched = unmatched[unmatched["Technology"].isin(["Solar", "Wind"])].copy()
    unmatched = unmatched.dropna(subset=["GSPGroup", "Latitude", "Longitude"])

    unmatched["capacity_mw"] = unmatched["InstalledCapacity (MW)"].apply(_parse_capacity)
    unmatched = unmatched.dropna(subset=["capacity_mw"])
    unmatched = unmatched[unmatched["capacity_mw"] > 0]

    meta_records = []
    gen_series: dict[int, pd.Series] = {}

    for idx, row in unmatched.iterrows():
        tech = "wind" if row["Technology"] == "Wind" else "solar"
        ts = estimate_generation_timeseries(
            lat=float(row["Latitude"]),
            lon=float(row["Longitude"]),
            capacity_mw=float(row["capacity_mw"]),
            tech=tech,
            era5_ds=era5_ds,
            start=start,
            end=end,
        )
        if ts.empty or float(ts.sum()) == 0.0:
            continue
        asset_id = int(idx)
        meta_records.append(
            {
                "asset_id": asset_id,
                "site_name": row["Site Name"],
                "lat": float(row["Latitude"]),
                "lon": float(row["Longitude"]),
                "tech": tech,
                "capacity_mw": float(row["capacity_mw"]),
                "gsp_group": row["GSPGroup"],
            }
        )
        gen_series[asset_id] = ts

    meta_df = pd.DataFrame(meta_records)

    if meta_df.empty:
        return meta_df, xr.DataArray(
            np.empty((0, 0)),
            coords={"asset": np.array([], dtype=int), "time": pd.DatetimeIndex([])},
            dims=["asset", "time"],
        )

    # All series share the same ERA5 time index — use the first as reference
    time_index = next(iter(gen_series.values())).index
    asset_ids = meta_df["asset_id"].values

    G = xr.DataArray(
        np.stack([gen_series[aid].reindex(time_index, fill_value=0.0).values for aid in asset_ids]),
        coords={"asset": asset_ids, "time": time_index},
        dims=["asset", "time"],
    )
    return meta_df, G


def load_supplier_units(
    catalogue_path: str | Path,
    missing_path: str | Path,
) -> pd.DataFrame:
    """Return supplier-type BM units with their GSP group, merging both catalogues.

    Loads the Elexon API catalogue and the NETA-sourced missing-units catalogue,
    deduplicates on bm_unit_id, and returns a DataFrame with columns:
        bm_unit_id, gsp_group
    """
    # --- Elexon API catalogue ---
    cat = pd.read_parquet(catalogue_path)
    api_supplier = cat[(cat["bmUnitType"] == "S") & cat["gspGroupId"].notna()].copy()
    api_df = api_supplier[["elexonBmUnit", "gspGroupId"]].rename(
        columns={"elexonBmUnit": "bm_unit_id", "gspGroupId": "gsp_group"}
    )

    # --- NETA missing-units catalogue ---
    # BM Unit Type contains "(G)" (default supplier) or "(S)" (specific supplier)
    missing = pd.read_parquet(missing_path)
    supplier_mask = missing["BM Unit Type"].str.contains(r"\(G\)|\(S\)", regex=True, na=False)
    missing_supplier = missing[supplier_mask & missing["GSP Group"].notna()].copy()
    # Extract GSP group ID from e.g. "Eastern (_A)" → "_A"
    missing_supplier = missing_supplier.copy()
    missing_supplier["gsp_group"] = missing_supplier["GSP Group"].str.extract(r"\((_[A-Z])\)")
    missing_supplier = missing_supplier[missing_supplier["gsp_group"].notna()]
    missing_df = missing_supplier[["elexonBmUnit", "gsp_group"]].rename(
        columns={"elexonBmUnit": "bm_unit_id"}
    )

    combined = pd.concat([api_df, missing_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["bm_unit_id"])
    return combined.reset_index(drop=True)


def compute_supplier_generation(
    supplier_ids: list[str],
    b1610_dir: str | Path,
    start: str,
    end: str,
) -> xr.DataArray:
    """Compute half-hourly positive generation (MW) for supplier BM units.

    Returns xr.DataArray with dims [supplier, time].
    """
    b1610_dir = Path(b1610_dir)
    dates = pd.date_range(start, end, freq="D")
    supplier_set = set(supplier_ids)

    frames = []
    for date in dates:
        path = b1610_dir / f"b1610_{date.date()}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(
            path, columns=["bmUnit", "settlementDate", "settlementPeriod", "quantity"]
        )
        df = df[df["bmUnit"].isin(supplier_set)]
        if df.empty:
            continue
        df = df.copy()
        df["time"] = pd.to_datetime(df["settlementDate"]) + pd.to_timedelta(
            (df["settlementPeriod"] - 1) * 30, unit="min"
        )
        frames.append(df[["bmUnit", "time", "quantity"]])

    if not frames:
        return xr.DataArray(
            np.zeros((len(supplier_ids), 0)),
            coords={"supplier": supplier_ids, "time": pd.DatetimeIndex([])},
            dims=["supplier", "time"],
        )

    all_data = pd.concat(frames, ignore_index=True)
    all_data["quantity"] = all_data["quantity"].clip(lower=0.0) * 2  # MWh per period → MW

    pivot = all_data.pivot_table(index="time", columns="bmUnit", values="quantity", aggfunc="sum")
    pivot = pivot.reindex(columns=supplier_ids, fill_value=0.0).fillna(0.0)
    pivot.index = pd.DatetimeIndex(pivot.index)
    pivot = pivot.sort_index()

    return xr.DataArray(
        pivot.values.T,  # [supplier, time]
        coords={"supplier": supplier_ids, "time": pivot.index},
        dims=["supplier", "time"],
    )


# ---------------------------------------------------------------------------
# MILP solver
# ---------------------------------------------------------------------------


def solve_gsp_assignment(
    G: xr.DataArray,
    B: xr.DataArray,
) -> dict[int, str]:
    """Solve the assignment MILP for one GSP group.

    Args:
        G: estimated generation [asset, time] in MW per half-hour.
        B: observed generation [supplier, time] in MW per half-hour.

    Returns:
        dict {asset_id: bm_unit_id} for assigned assets.
    """
    # Drop assets/suppliers with zero total generation
    G = G.sel(asset=G.sum("time") > 0)
    B = B.sel(supplier=B.sum("time") > 0)

    breakpoint()

    if G.sizes["asset"] == 0 or B.sizes["supplier"] == 0:
        return {}

    # Align to common time index
    G, B = xr.align(G, B, join="inner")

    if G.sizes["time"] == 0:
        return {}

    asset_ids = G.coords["asset"].values.tolist()
    supplier_ids = B.coords["supplier"].values.tolist()
    time_coords = G.coords["time"]

    m = linopy.Model()

    x = m.add_variables(
        binary=True, coords=[asset_ids, supplier_ids], dims=["asset", "supplier"], name="x"
    )
    r = m.add_variables(
        lower=0.0, coords=[supplier_ids, time_coords], dims=["supplier", "time"], name="r"
    )

    # Each asset assigned to at most one supplier
    m.add_constraints(x.sum("supplier") <= 1, name="one_per_asset")

    # assigned[supplier, time] = Σ_i x[i,j] * G[i,t]
    assigned = (x * G).sum("asset")

    # Linearise absolute residual: r[j,t] ≥ |assigned[j,t] - B[j,t]|
    m.add_constraints(r >= assigned - B, name="residual_pos")
    m.add_constraints(r + assigned >= B, name="residual_neg")

    # Minimise total absolute residual summed over suppliers and time
    m.add_objective(r.sum())

    m.solve(
        "highs",
        solver_options={"mip_rel_gap": 0.05},  # 5% optimality gap
        io_api="direct",
    )

    if m.termination_condition != "optimal":
        logger.warning("MILP did not find an optimal solution (status=%s)", m.termination_condition)
        return {}

    x_sol = m.solution["x"]
    result: dict[int, str] = {}
    for asset_id in asset_ids:
        for supplier_id in supplier_ids:
            if float(x_sol.sel(asset=asset_id, supplier=supplier_id)) > 0.5:
                result[int(asset_id)] = str(supplier_id)
                break

    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_assignment(
    data_path: str | Path,
    start: str,
    end: str,
    gsp_group: str = "all",
    output_path: str | Path = "data/assignment.json",
    era5_path: str | Path | None = None,
) -> None:
    """Run the asset-to-supplier MILP assignment.

    Args:
        data_path:   Root data directory.
        start:       Start date (YYYY-MM-DD, inclusive).
        end:         End date (YYYY-MM-DD, inclusive).
        gsp_group:   GSP group ID (e.g. '_A') or 'all' to run every group.
        output_path: Where to write the JSON assignment result.
        era5_path:   Path to ERA5 NetCDF (defaults to data_path/era5_uk_2026_jan_feb.nc).
    """
    from prism.met import load_era5

    data_path = Path(data_path)
    output_path = Path(output_path)

    if era5_path is None:
        era5_path = data_path / "era5_uk_2026_jan_feb.nc"

    logger.info("Loading ERA5 from %s", era5_path)
    era5_ds = load_era5(era5_path)

    logger.info("Loading unmatched assets …")
    meta_df, G_all = load_unmatched_assets(
        dukes_path=data_path / "dukes_clean.csv",
        matches_path=data_path / "matches.csv",
        era5_ds=era5_ds,
        start=start,
        end=end,
    )
    logger.info("  %d unmatched wind/solar assets", len(meta_df))

    logger.info("Loading supplier BM units …")
    suppliers_df = load_supplier_units(
        catalogue_path=data_path / "bm_unit_catalogue.parquet",
        missing_path=data_path / "missing_bm_unit_details.parquet",
    )

    # Which GSP groups to solve
    if gsp_group == "all":
        gsp_groups = sorted(meta_df["gsp_group"].dropna().unique().tolist())
    else:
        gsp_groups = [gsp_group]

    # Pre-compute supplier generation timeseries for relevant groups
    relevant_supplier_ids = suppliers_df[suppliers_df["gsp_group"].isin(gsp_groups)][
        "bm_unit_id"
    ].tolist()
    logger.info(
        "Computing generation timeseries for %d supplier units …", len(relevant_supplier_ids)
    )
    B_all = compute_supplier_generation(
        supplier_ids=relevant_supplier_ids,
        b1610_dir=data_path / "b1610",
        start=start,
        end=end,
    )

    suppliers_df = suppliers_df[suppliers_df["gsp_group"].isin(gsp_groups)].copy()

    # Solve per GSP group
    assignment: dict[str, str] = {}  # asset_id (str) → bm_unit_id
    for gsp in gsp_groups:
        group_asset_ids = meta_df.loc[meta_df["gsp_group"] == gsp, "asset_id"].values.tolist()
        group_supplier_ids = suppliers_df.loc[
            suppliers_df["gsp_group"] == gsp, "bm_unit_id"
        ].values.tolist()

        if not group_asset_ids or not group_supplier_ids:
            logger.info("GSP %s: skipping (no assets or no suppliers).", gsp)
            continue

        G_group = G_all.sel(asset=group_asset_ids)
        B_group = B_all.sel(
            supplier=[s for s in group_supplier_ids if s in B_all.coords["supplier"].values]
        )

        logger.info(
            "GSP %s: %d assets, %d suppliers, %d time steps",
            gsp,
            G_group.sizes["asset"],
            B_group.sizes["supplier"],
            G_group.sizes["time"],
        )

        result = solve_gsp_assignment(G_group, B_group)
        logger.info("  Assigned %d / %d assets.", len(result), len(group_asset_ids))
        for asset_id, bm_unit_id in result.items():
            assignment[str(asset_id)] = bm_unit_id

    # Enrich output with asset metadata
    asset_meta = meta_df.set_index("asset_id")
    output: dict[str, dict] = {}
    for aid_str, bm_unit_id in assignment.items():
        aid = int(aid_str)
        if aid in asset_meta.index:
            meta = asset_meta.loc[aid].to_dict()
            estimated_generation = float(G_all.sel(asset=aid).sum())
        else:
            meta = {}
            estimated_generation = 0.0
        clean_meta = {
            k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in meta.items()
        }
        output[aid_str] = {
            "bm_unit_id": bm_unit_id,
            "estimated_generation": estimated_generation,
            **clean_meta,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    logger.info("Saved %d assignments to %s", len(output), output_path)
