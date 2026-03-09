"""Script 3: Reproject DUKES, backfill missing, and join to GSP regions.

Converts X/Y coordinates from EPSG 27700 to EPSG 4326, backfills missing/incorrect
coordinates from extra_locations.csv, and spatially joins GSP region data.
"""

import geopandas as gpd
import pandas as pd
from pyproj import Transformer

DATA_DIR = "data"
DUKES_PATH = f"{DATA_DIR}/dukes_5_11.csv"
EXTRA_LOCATIONS_PATH = f"{DATA_DIR}/extra_locations.csv"
GSP_PATH = f"{DATA_DIR}/GSP_regions_4326_20250109_simplified.geojson"
OUTPUT_PATH = f"{DATA_DIR}/dukes_clean.csv"


def main() -> None:
    # --- Load DUKES ---
    df = pd.read_csv(DUKES_PATH)
    print(f"Loaded DUKES: {len(df)} rows")

    # --- Convert EPSG 27700 → 4326 for rows with valid (non-zero) coordinates ---
    transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    has_coords = (df["X-Coordinate"] != 0) & (df["Y-Coordinate"] != 0)
    lon, lat = transformer.transform(
        df.loc[has_coords, "X-Coordinate"].values,
        df.loc[has_coords, "Y-Coordinate"].values,
    )
    df["Latitude"] = None
    df["Longitude"] = None
    df.loc[has_coords, "Longitude"] = lon
    df.loc[has_coords, "Latitude"] = lat

    # --- Backfill / overwrite from extra_locations ---
    extra = pd.read_csv(EXTRA_LOCATIONS_PATH)
    # Strip surrounding quotes from site names introduced by CSV formatting
    extra["Site Name"] = extra["Site Name"].str.strip().str.strip('"')
    extra["Company Name [note 30]"] = extra["Company Name [note 30]"].str.strip()

    df = df.merge(
        extra.rename(columns={"Latitude": "Lat_extra", "Longitude": "Lon_extra"}),
        on=["Company Name [note 30]", "Site Name"],
        how="left",
    )
    matched = df["Lat_extra"].notna()
    df.loc[matched, "Latitude"] = df.loc[matched, "Lat_extra"]
    df.loc[matched, "Longitude"] = df.loc[matched, "Lon_extra"]
    df = df.drop(columns=["Lat_extra", "Lon_extra"])
    print(f"Backfilled {matched.sum()} rows from extra_locations")

    # --- Drop rows still missing coordinates ---
    missing = df["Latitude"].isna()
    if missing.any():
        print(f"Warning: {missing.sum()} rows still have no coordinates — dropping")
        df = df[~missing].copy()

    # --- Build GeoDataFrame from DUKES points ---
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
        crs="EPSG:4326",
    )

    # --- Load and dissolve GSP regions to GSPGroup ---
    gsp = gpd.read_file(GSP_PATH)
    gsp_dissolved = gsp.dissolve(by="GSPGroup").reset_index()[["GSPGroup", "geometry"]]
    print(f"GSP groups after dissolve: {len(gsp_dissolved)}")

    # --- Spatial join ---
    gdf_joined = gpd.sjoin(gdf, gsp_dissolved, how="left", predicate="within")
    gdf_joined = gdf_joined.drop(columns=["geometry", "index_right"])
    print(f"Rows after spatial join: {len(gdf_joined)}")
    unmatched = gdf_joined["GSPGroup"].isna().sum()
    if unmatched:
        print(f"Warning: {unmatched} rows did not fall within any GSP region")

    # --- Save ---
    gdf_joined.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved cleaned DUKES data to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
