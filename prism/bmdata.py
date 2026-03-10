"""Loading and joining balancing mechanism data."""

from pathlib import Path

import pandas as pd


def load_b1610(
    b1610_dir: str | Path,
    bm_units: list[str],
    start: str,
    end: str,
) -> pd.DataFrame:
    """Load B1610 half-hourly generation data for the given BM units and date range.

    Returns a DataFrame with a DatetimeIndex (period start times) and a single
    'quantity' column (sum across all requested BM units, in MW).
    """
    b1610_dir = Path(b1610_dir)
    dates = pd.date_range(start, end, freq="D")

    frames = []
    for date in dates:
        path = b1610_dir / f"b1610_{date.date()}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(
            path, columns=["bmUnit", "settlementDate", "settlementPeriod", "quantity"]
        )
        df = df[df["bmUnit"].isin(bm_units)]
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame({"quantity": pd.Series(dtype=float)})

    result = pd.concat(frames, ignore_index=True)

    # Period 1 ends at 00:30, so period start = (period - 1) * 30 min from midnight
    result["datetime"] = pd.to_datetime(result["settlementDate"]) + pd.to_timedelta(
        (result["settlementPeriod"] - 1) * 30, unit="min"
    )

    # Sum across all BM units for each half-hour
    agg = result.groupby("datetime")["quantity"].sum().sort_index()
    agg.index = pd.DatetimeIndex(agg.index)
    return agg.rename("quantity").to_frame()


def load_unit_details(catalogue_path: str | Path, bm_unit: str) -> dict | None:
    """Load BM unit details from the Elexon catalogue parquet. Returns None if not found."""
    df = pd.read_parquet(catalogue_path)
    match = df[df["elexonBmUnit"] == bm_unit]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def load_matches(matches_path: str | Path) -> pd.DataFrame:
    """Load DUKES-to-BM unit matches. Returns DataFrame with dukes_site_name, bm_unit_id."""
    df = pd.read_csv(matches_path, index_col=0)
    return df[["dukes_site_name", "bm_unit_id"]]
