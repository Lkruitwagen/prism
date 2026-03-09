"""Script 1: Fetch the BM Unit catalogue from the Elexon BMRS API and save as parquet."""

import pathlib

import pandas as pd
import requests

API_URL = "https://data.elexon.co.uk/bmrs/api/v1/reference/bmunits/all"
OUTPUT_PATH = pathlib.Path(__file__).parent.parent / "data" / "bm_unit_catalogue.parquet"


def fetch_bm_unit_catalogue() -> pd.DataFrame:
    response = requests.get(API_URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    return pd.DataFrame(data)


def main() -> None:
    print(f"Fetching BM Unit catalogue from {API_URL} ...")
    df = fetch_bm_unit_catalogue()
    print(f"Retrieved {len(df)} BM units.")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
