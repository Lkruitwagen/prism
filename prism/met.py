"""Loading and sampling ERA5 meteorological data."""

from pathlib import Path

import pandas as pd
import xarray as xr


def load_era5(path: str | Path) -> xr.Dataset:
    """Load ERA5 NetCDF dataset."""
    return xr.open_dataset(path)


def interpolate(ds: xr.Dataset, lat: float, lon: float) -> xr.Dataset:
    """Bilinearly interpolate ERA5 to an exact lat/lon."""
    return ds.interp(latitude=lat, longitude=lon)


def get_wind_speed(ds: xr.Dataset, lat: float, lon: float) -> pd.Series:
    """Return 100m wind speed time series (m/s) interpolated to the given lat/lon."""
    point = interpolate(ds, lat, lon)
    ts = point["100m_wind_speed"].to_series()
    ts.index = pd.DatetimeIndex(ts.index)
    return ts


def get_solar_radiation(ds: xr.Dataset, lat: float, lon: float) -> pd.Series:
    """Return surface solar radiation downwards (W/m²) interpolated to the given lat/lon."""
    point = interpolate(ds, lat, lon)
    ts = point["surface_solar_radiation_downwards"].to_series()
    ts.index = pd.DatetimeIndex(ts.index)
    return ts
