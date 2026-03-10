"""Script 5: Interactive DUKES-to-BM-unit matching interface.

Iterates through DUKES power stations (largest installed capacity first) and
proposes candidate BM unit matches using partial Levenshtein distance (rapidfuzz).
Results are persisted continuously to data/matches.json so the script can be
stopped and restarted without losing progress.

Usage:
    uv run python scripts/match_dukes_to_bm_units.py

Commands at the prompt:
    1,3,5   — accept BM units numbered 1, 3 and 5 from the candidate table
    s       — skip this plant (mark as no BM unit match)
    q       — save and quit
"""

import json
import pathlib
import re
import sys

import pandas as pd
import pyarrow.dataset as ds
from rapidfuzz import fuzz, process
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
DUKES_PATH = DATA_DIR / "dukes_clean.csv"
CATALOGUE_PATH = DATA_DIR / "bm_unit_catalogue.parquet"
MISSING_PATH = DATA_DIR / "missing_bm_unit_details.parquet"
NETALIST_PATH = DATA_DIR / "netalist.html"
B1610_DIR = DATA_DIR / "b1610"
MATCHES_PATH = DATA_DIR / "matches.json"

TOP_N = 15

console = Console()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def parse_capacity(val) -> float | None:
    """Parse a capacity string/value to float MW, returning None if unparseable."""
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if s in ("", "-", "N/A", "n/a", "nan", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_neta_names() -> dict[str, str]:
    """Parse netalist.html and return {elexonBmUnit: station_name}.

    Each <option> text has the form "<GSP Group> - <Station Name> (<BM_UNIT_ID>)".
    We extract the Station Name (dropping the GSP group prefix).
    """
    html = NETALIST_PATH.read_text(encoding="utf-8")
    names: dict[str, str] = {}
    for m in re.finditer(r"<option[^>]*>([^<]+)</option>", html):
        text = m.group(1).strip()
        if not (text.endswith(")") and "(" in text):
            continue
        bm_id = text.rsplit("(", 1)[-1].rstrip(")")
        name_part = text.rsplit("(", 1)[0].strip()
        names[bm_id] = name_part.strip()
    return names


def load_b1610_stats() -> pd.DataFrame:
    """Compute max/min observed quantity per BM unit across all B1610 parquet files."""
    console.print("[dim]Scanning B1610 generation files...[/dim]")
    dataset = ds.dataset(str(B1610_DIR), format="parquet")
    table = dataset.to_table(columns=["bmUnit", "quantity"])
    # Filter to non-zero quantities only
    import pyarrow.compute as pc

    table = table.filter(pc.greater(pc.abs(table["quantity"]), 0))
    agg = table.group_by("bmUnit").aggregate([("quantity", "max"), ("quantity", "min")])
    df = agg.to_pandas().rename(
        columns={"bmUnit": "elexonBmUnit", "quantity_max": "max_qty", "quantity_min": "min_qty"}
    )
    # Convert MWh per half-hour → MW
    df["max_qty"] *= 2
    df["min_qty"] *= 2
    console.print(f"[dim]  {len(df)} BM units with observed generation.[/dim]")
    return df.set_index("elexonBmUnit")


def load_bm_units(b1610_stats: pd.DataFrame) -> pd.DataFrame:
    """Load catalogue + missing-details BM units into a unified, deduplicated dataframe."""
    cat = pd.read_parquet(CATALOGUE_PATH)
    cat_df = pd.DataFrame(
        {
            "elexonBmUnit": cat["elexonBmUnit"],
            "nationalGridBmUnit": cat.get("nationalGridBmUnit", pd.Series(dtype=str)),
            "bmUnitName": cat.get("bmUnitName", pd.Series(dtype=str)),
            "leadPartyName": cat.get("leadPartyName", pd.Series(dtype=str)),
            "fuelType": cat.get("fuelType", pd.Series(dtype=str)),
            "gspGroupId": cat.get("gspGroupId", pd.Series(dtype=str)),
            "generationCapacity": cat["generationCapacity"].apply(parse_capacity),
            "source": "catalogue",
        }
    )

    miss = pd.read_parquet(MISSING_PATH)
    miss_df = pd.DataFrame(
        {
            "elexonBmUnit": miss["elexonBmUnit"],
            "nationalGridBmUnit": miss.get("NGC BM Unit Name", pd.Series(dtype=str)),
            "bmUnitName": miss.get("BM Unit Name", pd.Series(dtype=str)),
            "leadPartyName": miss.get("BSC Party", pd.Series(dtype=str)),
            "fuelType": pd.Series([None] * len(miss), dtype=object),
            "gspGroupId": miss.get("GSP Group", pd.Series(dtype=str)),
            "generationCapacity": miss["Generation Capacity"].apply(parse_capacity),
            "source": "neta",
        }
    )

    # Catalogue entries take priority; drop NETA duplicates
    bm = pd.concat([cat_df, miss_df], ignore_index=True)
    bm = bm.drop_duplicates(subset=["elexonBmUnit"], keep="first")
    bm = bm.set_index("elexonBmUnit")

    # Join NETA station names from netalist.html
    neta_names = parse_neta_names()
    bm["neta_name"] = bm.index.map(neta_names)

    # Join observed generation stats
    bm = bm.join(b1610_stats, how="left")
    console.print(
        f"[dim]  {len(bm)} BM units loaded ({len(cat_df)} catalogue, {len(miss_df)} NETA).[/dim]"
    )
    return bm


def load_dukes() -> pd.DataFrame:
    df = pd.read_csv(DUKES_PATH)
    df["_capacity"] = df["InstalledCapacity (MW)"].apply(parse_capacity)
    df = df.sort_values("_capacity", ascending=False, na_position="last").reset_index(drop=True)
    return df


def load_matches() -> dict:
    if MATCHES_PATH.exists():
        return json.loads(MATCHES_PATH.read_text())
    return {}


def save_matches(matches: dict) -> None:
    MATCHES_PATH.write_text(json.dumps(matches, indent=2))


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _safe_str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    return "" if s == "nan" else s


def score_bm_units(plant: pd.Series, bm_units: pd.DataFrame) -> pd.DataFrame:
    """Return the top-N BM units by partial Levenshtein similarity to the plant."""
    query = _safe_str(plant.get("Site Name"))

    # Match Site Name against neta_name (falls back to bmUnitName if absent)
    candidate_strings: dict[str, str] = {
        elexon_id: _safe_str(row.get("neta_name")) or _safe_str(row.get("bmUnitName"))
        for elexon_id, row in bm_units.iterrows()
    }

    results = process.extract(query, candidate_strings, scorer=fuzz.partial_ratio, limit=TOP_N)
    # results: list of (matched_string, score, key)

    top_ids = [key for _, _, key in results]
    scores = {key: score for _, score, key in results}

    top_bm = bm_units.loc[top_ids].copy()
    top_bm["score"] = [scores[k] for k in top_bm.index]
    top_bm = top_bm.reset_index()  # elexonBmUnit becomes a column
    return top_bm


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _fmt_cap(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "[dim]-[/dim]"
    return f"{val:.0f}"


def display_plant(plant: pd.Series, position: int, total: int) -> None:
    cap = plant.get("_capacity")
    cap_str = f"{cap:.1f} MW" if cap is not None and not pd.isna(cap) else "-"
    lines = [
        f"[bold]{_safe_str(plant.get('Site Name'))}[/bold]"
        f"  |  {_safe_str(plant.get('Company Name [note 30]'))}",
        f"Technology: [cyan]{_safe_str(plant.get('Technology'))}[/cyan]"
        f"  |  Fuel: {_safe_str(plant.get('Primary Fuel'))}"
        f"  |  Capacity: [yellow]{cap_str}[/yellow]",
        f"GSP: {_safe_str(plant.get('GSPGroup')) or '-'}"
        f"  |  Country: {_safe_str(plant.get('Country')) or '-'}"
        f"  |  Region: {_safe_str(plant.get('Region')) or '-'}",
    ]
    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold]Plant {position}/{total}[/bold]",
            border_style="blue",
        )
    )


def display_candidates(candidates: pd.DataFrame) -> None:
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        expand=True,
        padding=(0, 1),
    )
    table.add_column("#", style="bold white", width=3, no_wrap=True)
    table.add_column("elexonBmUnit", style="cyan", width=18, no_wrap=True)
    table.add_column("NETA Name", width=26)
    table.add_column("Lead Party", width=22)
    table.add_column("Fuel", width=10)
    table.add_column("GSP", width=6, no_wrap=True)
    table.add_column("GenCap\nMW", justify="right", width=8)
    table.add_column("MaxObs\nMW", justify="right", width=8)
    table.add_column("MinObs\nMW", justify="right", width=8)
    table.add_column("Score", justify="right", width=5)

    for i, (_, row) in enumerate(candidates.iterrows(), 1):
        neta_name = _safe_str(row.get("neta_name")) or _safe_str(row.get("bmUnitName")) or "-"
        table.add_row(
            str(i),
            _safe_str(row.get("elexonBmUnit")) or "-",
            neta_name[:26],
            (_safe_str(row.get("leadPartyName")) or "-")[:22],
            (_safe_str(row.get("fuelType")) or "-")[:10],
            (_safe_str(row.get("gspGroupId")) or "-")[:6],
            _fmt_cap(row.get("generationCapacity")),
            _fmt_cap(row.get("max_qty")),
            _fmt_cap(row.get("min_qty")),
            str(int(row["score"])),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    console.rule("[bold blue]DUKES → BM Unit Matching[/bold blue]")

    b1610_stats = load_b1610_stats()
    bm_units = load_bm_units(b1610_stats)
    dukes = load_dukes()
    matches = load_matches()

    already_done = len(matches)
    console.print(
        f"[green]Loaded {len(dukes)} DUKES plants, {len(bm_units)} BM units.[/green]"
        f" {already_done} plants already matched."
    )
    console.print(
        "[dim]At the prompt: comma-separated numbers to accept matches "
        "(e.g. [bold]1,3[/bold]), [bold]s[/bold] = no match, [bold]q[/bold] = save & quit[/dim]"
    )
    console.print()

    position = already_done  # running count for display
    for idx, plant in dukes.iterrows():
        plant_key = str(idx)
        if plant_key in matches:
            continue

        position += 1
        display_plant(plant, position, len(dukes))
        candidates = score_bm_units(plant, bm_units)
        display_candidates(candidates)

        while True:
            response = Prompt.ask("[bold]Select matches[/bold]").strip().lower()

            if response == "q":
                save_matches(matches)
                console.print("[yellow]Progress saved. Goodbye.[/yellow]")
                sys.exit(0)

            elif response == "s":
                matches[plant_key] = {
                    "site_name": _safe_str(plant.get("Site Name")),
                    "bm_units": [],
                }
                save_matches(matches)
                break

            else:
                try:
                    selected = [int(x.strip()) for x in response.split(",") if x.strip()]
                except ValueError:
                    console.print("[red]Invalid input — enter numbers, 's', or 'q'.[/red]")
                    continue

                if not selected:
                    console.print("[red]Please enter at least one number, 's', or 'q'.[/red]")
                    continue

                if any(n < 1 or n > len(candidates) for n in selected):
                    console.print(f"[red]Numbers must be between 1 and {len(candidates)}.[/red]")
                    continue

                selected_bm_units = [
                    _safe_str(candidates.iloc[n - 1]["elexonBmUnit"]) for n in selected
                ]
                matches[plant_key] = {
                    "site_name": _safe_str(plant.get("Site Name")),
                    "bm_units": selected_bm_units,
                }
                save_matches(matches)
                break

        console.print()

    console.print(
        "[bold green]All plants processed! Results saved to data/matches.json.[/bold green]"
    )
    save_matches(matches)


if __name__ == "__main__":
    main()
