"""Script 2: Fetch B1610 actual generation output per BM unit from the Elexon BMRS API."""

import argparse
import pathlib
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

API_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets/B1610/stream"
OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "data" / "b1610"
WAIT_SECONDS = 30


def day_start_iso(d: date) -> str:
    return datetime(d.year, d.month, d.day, 0, 0, tzinfo=timezone.utc).isoformat()


def day_end_iso(d: date) -> str:
    return datetime(d.year, d.month, d.day, 23, 59, tzinfo=timezone.utc).isoformat()


def fetch_day(from_iso: str, to_iso: str) -> pd.DataFrame:
    response = requests.get(API_URL, params={"from": from_iso, "to": to_iso}, timeout=60)
    response.raise_for_status()
    return pd.DataFrame(response.json())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch B1610 generation data from Elexon BMRS API."
    )
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD, inclusive)")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    current = start
    while current <= end:
        from_iso = day_start_iso(current)
        to_iso_str = day_end_iso(current)

        print(f"Fetching {current} ({from_iso} → {to_iso_str}) ...")
        df = fetch_day(from_iso, to_iso_str)
        print(f"  Retrieved {len(df)} records.")

        out_path = OUTPUT_DIR / f"b1610_{current.isoformat()}.parquet"
        df.to_parquet(out_path, index=False)
        print(f"  Saved to {out_path}")

        current = current + timedelta(days=1)
        if current <= end:
            print(f"  Waiting {WAIT_SECONDS}s before next request ...")
            time.sleep(WAIT_SECONDS)

    print("Done.")


if __name__ == "__main__":
    main()
