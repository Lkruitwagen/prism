# Collecting a cube of meteorological data

Our eventual aim is to model UK energy supply directly from UK weather data.
We want to sample a cube of UK weather data as the input to our power functions.

We can sample hourly weather data from the ERA5 corpus mirrored on Google Cloud Storage.
We'll need xarray and zarr to read the data.
Prepare a script to do the following and put it in @scripts/:
- load the era5 zarr archive at `gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3`.
- load the following variables:
  - `100m_u_component_of_wind`
  - `100m_v_component_of_wind`
  - `2m_temperature`
  - `surface_solar_radiation_downwards`
  - `total_preciptiation`
- create a new variable: `100m_wind_speed`, the magnitude of the combined `u` and `v` vectors.
- roll the longitude to [-180,180]
- filter for the first two months of 2026: [2026-01-01, 2026-02-28]
- filter for approximate lat/lon extents of the UK: lat: [50,60], lon: [-10,2]
- interpolate the datacube to half-hourly  
- compute the datacube, loading it into memory
- save the datacube to an nc file so we can load the contiguous data easily.

Plan first and ask any clarification necessary.
Update clarifications on this document.
When your're done executing, update the @CLAUDE.md with anything you've learned.