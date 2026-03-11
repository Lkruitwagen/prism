"""Daily inference: estimate plant-level generation and collect BM unit quantities."""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from prism import solar as solar_module
from prism import wind as wind_module
from prism.fetch import fetch_b1610_day, fetch_era5_day
from prism.fit import predict
from prism.met import get_solar_radiation, get_wind_speed

log = logging.getLogger(__name__)


def _load_fits(fits_wind_path: Path, fits_solar_path: Path) -> list[dict]:
    """Load and merge wind and solar fits into a single list."""
    records = []
    for path in [fits_wind_path, fits_solar_path]:
        if path.exists():
            records.extend(json.loads(path.read_text()))
    return records


def _fit_params_to_log_params(fit_params: dict) -> np.ndarray:
    """Convert human-readable fit_params dict back to log-param numpy array."""
    plant_type = fit_params["plant_type"]
    pnames = wind_module.param_names() if plant_type == "wind" else solar_module.param_names()
    return np.array([np.log(fit_params[name]) for name in pnames])


def _safe_float(val: float) -> float:
    """Return 0.0 for NaN/Inf, otherwise the value."""
    return 0.0 if (np.isnan(val) or np.isinf(val)) else float(val)


def _to_period_dict(series: pd.Series, d: date) -> dict[str, float]:
    """Convert a half-hourly Series (DatetimeIndex) to {str(period): MW} for one day."""
    result = {}
    for ts, val in series.items():
        ts = pd.Timestamp(ts)
        if ts.date() == d:
            period = ts.hour * 2 + ts.minute // 30 + 1
            result[str(period)] = _safe_float(val)
    return result


def run_inference(
    date_str: str,
    data_path: Path,
    fits_wind_path: Path,
    fits_solar_path: Path,
    assignment_path: Path,
) -> dict[str, Any]:
    """Run inference for a given date.

    Returns a dict with:
      - date: ISO date string
      - bm_unit_quantities: {bm_unit_id: {str(period): MW}}
      - plant_generation: list of plant generation records
    """
    d = date.fromisoformat(date_str)
    b1610_dir = data_path / "b1610"

    # --- Fetch B1610 data if not already cached ---
    b1610_path = b1610_dir / f"b1610_{date_str}.parquet"
    if not b1610_path.exists():
        log.info("Fetching B1610 for %s...", date_str)
        fetch_b1610_day(d, b1610_dir)
    else:
        log.info("Using cached B1610 for %s", date_str)

    # --- Fetch ERA5 ---
    log.info("Fetching ERA5 for %s...", date_str)
    era5_ds = fetch_era5_day(d)

    # --- Load fits ---
    fits = _load_fits(fits_wind_path, fits_solar_path)
    log.info("Loaded %d fit records", len(fits))

    # --- Load assignment ---
    assignment: dict[str, dict] = {}
    if assignment_path.exists():
        assignment = json.loads(assignment_path.read_text())
    log.info("Loaded %d assigned unmatched plants", len(assignment))

    # --- Collect all BM units ---
    all_bm_units: set[str] = set()
    for record in fits:
        all_bm_units.update(record["bm_units"])
    for plant_info in assignment.values():
        all_bm_units.add(plant_info["bm_unit_id"])

    # --- Build per-unit B1610 quantities from raw parquet ---
    log.info("Loading B1610 quantities for %d BM units...", len(all_bm_units))
    raw_df = pd.read_parquet(
        b1610_path,
        columns=["bmUnit", "settlementDate", "settlementPeriod", "quantity"],
    )
    raw_df = raw_df[raw_df["bmUnit"].isin(all_bm_units)]

    bm_unit_quantities: dict[str, dict[str, float]] = {}
    for unit_id, group in raw_df.groupby("bmUnit"):
        bm_unit_quantities[str(unit_id)] = {
            str(int(row.settlementPeriod)): _safe_float(row.quantity) for row in group.itertuples()
        }

    # --- Plant generation estimates ---
    plant_generation = []

    # Matched plants (from fits JSON)
    for record in fits:
        bm_units = record["bm_units"]
        for fit_entry in record["fits"]:
            fit_params = fit_entry["fit_params"]
            if not fit_params.get("converged", False):
                continue

            plant_type = fit_params["plant_type"]
            lat = fit_entry["lat"]
            lon = fit_entry["lon"]

            try:
                log_params = _fit_params_to_log_params(fit_params)
            except (KeyError, ValueError) as e:
                log.warning("Skipping %s — could not convert fit_params: %s", bm_units, e)
                continue

            if plant_type == "wind":
                met_series = get_wind_speed(era5_ds, lat, lon)
                power_fn = wind_module.wind_power
            else:
                met_series = get_solar_radiation(era5_ds, lat, lon)
                power_fn = solar_module.solar_power

            met_day = met_series[met_series.index.date == d]
            if met_day.empty:
                continue

            predictions = predict(power_fn, log_params, met_day.values.astype(float))
            gen_dict = _to_period_dict(pd.Series(predictions, index=met_day.index), d)

            plant_generation.append(
                {
                    "bm_units": bm_units,
                    "lat": lat,
                    "lon": lon,
                    "plant_type": plant_type,
                    "source": "matched",
                    "generation": gen_dict,
                }
            )

    # Unmatched plants (from assignment JSON, use default power curve params)
    for dukes_idx, plant_info in assignment.items():
        tech = plant_info.get("tech", "").lower()
        capacity_mw = float(plant_info.get("capacity_mw", 10.0))
        lat = plant_info["lat"]
        lon = plant_info["lon"]

        if "wind" in tech:
            plant_type = "wind"
            met_series = get_wind_speed(era5_ds, lat, lon)
            power_fn = wind_module.wind_power
            log_params = wind_module.default_params(capacity_mw=capacity_mw)
        elif "solar" in tech or "pv" in tech:
            plant_type = "solar"
            met_series = get_solar_radiation(era5_ds, lat, lon)
            power_fn = solar_module.solar_power
            log_params = solar_module.default_params(capacity_mw=capacity_mw)
        else:
            continue

        met_day = met_series[met_series.index.date == d]
        if met_day.empty:
            continue

        predictions = predict(power_fn, log_params, met_day.values.astype(float))
        gen_dict = _to_period_dict(pd.Series(predictions, index=met_day.index), d)

        plant_generation.append(
            {
                "dukes_index": dukes_idx,
                "bm_unit_id": plant_info["bm_unit_id"],
                "site_name": plant_info.get("site_name", ""),
                "lat": lat,
                "lon": lon,
                "plant_type": plant_type,
                "capacity_mw": capacity_mw,
                "source": "unmatched",
                "generation": gen_dict,
            }
        )

    log.info(
        "Inference complete: %d BM units, %d plant records",
        len(bm_unit_quantities),
        len(plant_generation),
    )

    return {
        "date": date_str,
        "bm_unit_quantities": bm_unit_quantities,
        "plant_generation": plant_generation,
    }
