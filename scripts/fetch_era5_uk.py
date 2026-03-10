"""
Fetch ERA5 weather data cube for the UK, Jan-Feb 2026.

Source: gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3
Output: data/era5_uk_2026_jan_feb.nc
"""

import numpy as np
import pandas as pd
import xarray as xr

ZARR_PATH = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"

VARIABLES = [
    "100m_u_component_of_wind",
    "100m_v_component_of_wind",
    "2m_temperature",
    "surface_solar_radiation_downwards",
    "total_precipitation",
]

TIME_START = "2026-01-01"
TIME_END = "2026-02-28T23:00:00"

LAT_MIN, LAT_MAX = 50.0, 60.0
LON_MIN, LON_MAX = -10.0, 2.0

OUTPUT_PATH = "data/era5_uk_2026_jan_feb.nc"


def main():
    print(f"Opening ERA5 zarr store: {ZARR_PATH}")
    ds = xr.open_zarr(
        ZARR_PATH,
        storage_options={"token": "anon"},
        consolidated=True,
    )

    print("Available variables (first 20):", list(ds.data_vars)[:20])

    # Select only the variables we need
    ds = ds[VARIABLES]

    # Roll longitude from [0, 360] to [-180, 180]
    print("Rolling longitude to [-180, 180]...")
    ds = ds.assign_coords(longitude=(((ds.longitude + 180) % 360) - 180))
    ds = ds.sortby("longitude")

    # Filter time
    print(f"Filtering time: {TIME_START} to {TIME_END}")
    ds = ds.sel(time=slice(TIME_START, TIME_END))

    # Filter spatial extent (UK)
    print(f"Filtering lat [{LAT_MIN}, {LAT_MAX}], lon [{LON_MIN}, {LON_MAX}]...")
    ds = ds.sel(
        latitude=slice(LAT_MAX, LAT_MIN),  # ERA5 latitude is descending
        longitude=slice(LON_MIN, LON_MAX),
    )

    # Convert accumulated variables to flux (divide by 3600 s/hr)
    # ERA5 accumulations are J/m² (ssrd) and m (tp) per hour; dividing gives W/m² and m/s
    print("Converting accumulated variables to flux...")
    for var in ["surface_solar_radiation_downwards", "total_precipitation"]:
        ds[var] = ds[var] / 3600.0
        ds[var].attrs = {**ds[var].attrs, "units": "W m**-2" if "solar" in var else "m s**-1"}

    # Compute 100m wind speed magnitude
    print("Computing 100m wind speed...")
    ds["100m_wind_speed"] = np.sqrt(
        ds["100m_u_component_of_wind"] ** 2 + ds["100m_v_component_of_wind"] ** 2
    )
    ds["100m_wind_speed"].attrs = {
        "long_name": "100m wind speed",
        "units": "m s**-1",
    }

    # Interpolate to half-hourly (30 min intervals)
    print("Interpolating to half-hourly resolution...")
    time_halfhourly = pd.date_range(
        start=str(ds.time.values[0]),
        end=str(ds.time.values[-1]),
        freq="30min",
    )
    ds = ds.interp(time=time_halfhourly, method="linear")

    # Compute (load into memory)
    print("Computing dataset (loading into memory)...")
    ds = ds.compute()

    print("Dataset loaded. Shape summary:")
    for var in ds.data_vars:
        print(f"  {var}: {ds[var].shape}")

    # Save to NetCDF
    print(f"Saving to {OUTPUT_PATH}...")
    ds.to_netcdf(OUTPUT_PATH)
    print("Done.")


if __name__ == "__main__":
    main()
