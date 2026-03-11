"""Prepare plants.json for the UI from dukes_clean.csv and groups.json."""

import json
import math
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).parent.parent
DATA = REPO_ROOT / "data"


def parse_capacity(s: str) -> float:
    try:
        return float(str(s).strip())
    except (ValueError, TypeError):
        return 0.0


def main() -> None:
    dukes = pd.read_csv(DATA / "dukes_clean.csv")
    with open(DATA / "groups.json") as f:
        groups = json.load(f)

    dukes_idx_to_group: dict[str, str] = groups["dukes_idx_to_group"]

    plants = []
    for idx, row in dukes.iterrows():
        idx_str = str(idx)
        group_id = dukes_idx_to_group.get(idx_str)
        capacity_mw = parse_capacity(row["InstalledCapacity (MW)"])
        lat = row["Latitude"]
        lon = row["Longitude"]
        if math.isnan(lat) or math.isnan(lon):
            continue
        plants.append(
            {
                "idx": int(idx),
                "site_name": str(row["Site Name"]),
                "company": str(row["Company Name [note 30]"]),
                "technology": str(row["Technology"]),
                "capacity_mw": round(capacity_mw, 3),
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "gsp_group": str(row["GSPGroup"]) if pd.notna(row["GSPGroup"]) else None,
                "group_id": group_id,
            }
        )

    out = DATA / "plants.json"
    with open(out, "w") as f:
        json.dump(plants, f, separators=(",", ":"))
    print(f"Wrote {len(plants)} plants to {out}")


if __name__ == "__main__":
    main()
