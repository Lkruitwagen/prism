"""Functions for fetching B1610 and ERA5 data for a single day."""

from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

B1610_API_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets/B1610/stream"
ZARR_PATH = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
ERA5_VARIABLES = [
    "100m_u_component_of_wind",
    "100m_v_component_of_wind",
    "surface_solar_radiation_downwards",
]
LAT_MIN, LAT_MAX = 50.0, 60.0
LON_MIN, LON_MAX = -10.0, 2.0


def fetch_b1610_day(d: date | str, output_dir: Path) -> Path:
    """Fetch B1610 generation data for a single day and save as parquet.

    Returns the path to the saved parquet file.
    """
    if isinstance(d, str):
        d = date.fromisoformat(d)

    from_iso = datetime(d.year, d.month, d.day, 0, 0, tzinfo=timezone.utc).isoformat()
    to_iso = datetime(d.year, d.month, d.day, 23, 59, tzinfo=timezone.utc).isoformat()

    response = requests.get(B1610_API_URL, params={"from": from_iso, "to": to_iso}, timeout=60)
    response.raise_for_status()
    df = pd.DataFrame(response.json())

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"b1610_{d.isoformat()}.parquet"
    df.to_parquet(out_path, index=False)
    return out_path


def fetch_era5_day(d: date | str) -> xr.Dataset:
    """Fetch ERA5 weather data for a single day from the public GCS archive.

    Returns an in-memory xarray Dataset with 100m wind speed and surface solar
    radiation, interpolated to 30-minute resolution.
    """
    if isinstance(d, str):
        d = date.fromisoformat(d)

    time_start = f"{d.isoformat()}T00:00:00"
    time_end = f"{d.isoformat()}T23:00:00"

    ds = xr.open_zarr(
        ZARR_PATH,
        storage_options={"token": "anon"},
        consolidated=True,
    )
    ds = ds[ERA5_VARIABLES]

    # Roll longitude from [0, 360] to [-180, 180]
    ds = ds.assign_coords(longitude=(((ds.longitude + 180) % 360) - 180))
    ds = ds.sortby("longitude")

    ds = ds.sel(time=slice(time_start, time_end))
    ds = ds.sel(
        latitude=slice(LAT_MAX, LAT_MIN),  # ERA5 latitude is descending
        longitude=slice(LON_MIN, LON_MAX),
    )

    # Convert accumulated SSRD (J/m² per hour) to flux (W/m²)
    ds["surface_solar_radiation_downwards"] = ds["surface_solar_radiation_downwards"] / 3600.0

    # Compute 100m wind speed magnitude
    ds["100m_wind_speed"] = np.sqrt(
        ds["100m_u_component_of_wind"] ** 2 + ds["100m_v_component_of_wind"] ** 2
    )

    # Interpolate to half-hourly resolution
    time_hh = pd.date_range(start=time_start, end=time_end, freq="30min")
    ds = ds.interp(time=time_hh, method="linear")

    return ds.compute()
