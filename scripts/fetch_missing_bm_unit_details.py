"""Script 4: Fetch missing BM Unit details from netareports.com.

For BM units that appear in the B1610 generation data (with non-zero quantity)
but are absent from the Elexon reference catalogue, retrieve details from NETA.
"""

import pathlib
import time
from html.parser import HTMLParser

import pandas as pd
import requests

DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
B1610_DIR = DATA_DIR / "b1610"
CATALOGUE_PATH = DATA_DIR / "bm_unit_catalogue.parquet"
NETALIST_PATH = DATA_DIR / "netalist.html"
OUTPUT_PATH = DATA_DIR / "missing_bm_unit_details.parquet"

PAUSE_SECONDS = 5


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------


class NetaListParser(HTMLParser):
    """Parse the <select> element in netalist.html to extract BM unit → URL map."""

    def __init__(self) -> None:
        super().__init__()
        self.bm_unit_map: dict[str, str] = {}
        self._current_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "option":
            attr_dict = dict(attrs)
            self._current_url = attr_dict.get("value")

    def handle_data(self, data: str) -> None:
        if self._current_url:
            # BM Unit ID is the last parenthesised token, e.g. "(2__AALAB000)"
            data = data.strip()
            if data.endswith(")") and "(" in data:
                bm_unit_id = data.rsplit("(", 1)[-1].rstrip(")")
                self.bm_unit_map[bm_unit_id] = self._current_url

    def handle_endtag(self, tag: str) -> None:
        if tag == "option":
            self._current_url = None


class NetaBlobParser(HTMLParser):
    """Parse the detail table from a NETA BM unit page.

    The table has one row per attribute. The first <td> holds the <b> label;
    subsequent <td> cells hold values (possibly multiple time-period columns).
    We retain the last non-empty value for each attribute.
    """

    def __init__(self) -> None:
        super().__init__()
        self.record: dict[str, str] = {}
        self._in_table = False
        self._row_cells: list[str] = []
        self._current_cell: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            attr_dict = dict(attrs)
            if attr_dict.get("border") == "1":
                self._in_table = True
        elif tag == "tr" and self._in_table:
            self._row_cells = []
        elif tag == "td" and self._in_table:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._in_table:
            self._row_cells.append("".join(self._current_cell).strip())
            self._in_cell = False
        elif tag == "tr" and self._in_table:
            self._flush_row()
        elif tag == "table":
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)

    def _flush_row(self) -> None:
        cells = self._row_cells
        if len(cells) < 2:
            return
        label = cells[0].strip()
        # Last non-empty value across all columns
        values = [c for c in cells[1:] if c.strip()]
        value = values[-1] if values else ""
        if label:
            self.record[label] = value


def parse_neta_list(html: str) -> dict[str, str]:
    parser = NetaListParser()
    parser.feed(html)
    return parser.bm_unit_map


def parse_neta_blob(html: str) -> dict[str, str]:
    parser = NetaBlobParser()
    parser.feed(html)
    return parser.record


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def load_b1610_bm_units_with_nonzero_quantity() -> set[str]:
    """Return BM unit IDs from B1610 data that have any non-zero quantity."""
    frames = []
    for path in sorted(B1610_DIR.glob("*.parquet")):
        frames.append(pd.read_parquet(path, columns=["bmUnit", "quantity"]))
    if not frames:
        raise FileNotFoundError(f"No parquet files found in {B1610_DIR}")
    df = pd.concat(frames, ignore_index=True)
    nonzero = df[df["quantity"].abs() > 0]["bmUnit"].unique()
    return set(nonzero)


def load_catalogue_bm_units() -> set[str]:
    df = pd.read_parquet(CATALOGUE_PATH, columns=["elexonBmUnit"])
    return set(df["elexonBmUnit"].dropna().unique())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Loading NETA BM unit list from netalist.html ...")
    neta_list_html = NETALIST_PATH.read_text(encoding="utf-8")
    neta_map = parse_neta_list(neta_list_html)
    print(f"  Found {len(neta_map)} BM units in NETA list.")

    print("Loading B1610 generation data ...")
    b1610_units = load_b1610_bm_units_with_nonzero_quantity()
    print(f"  {len(b1610_units)} BM units with non-zero quantity in B1610.")

    print("Loading BM unit catalogue ...")
    catalogue_units = load_catalogue_bm_units()
    print(f"  {len(catalogue_units)} BM units in catalogue.")

    missing = b1610_units - catalogue_units
    print(f"  {len(missing)} BM units missing from catalogue.")

    # Intersect with those available in NETA
    to_fetch = sorted(missing & set(neta_map.keys()))
    no_neta = missing - set(neta_map.keys())
    print(f"  {len(to_fetch)} have a NETA page; {len(no_neta)} have no NETA entry.")

    records = []
    for i, bm_unit in enumerate(to_fetch):
        url = neta_map[bm_unit]
        print(f"[{i + 1}/{len(to_fetch)}] Fetching {bm_unit} from {url} ...")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            record = parse_neta_blob(resp.text)
            record["elexonBmUnit"] = bm_unit
            record["neta_url"] = url
            records.append(record)
        except requests.RequestException as exc:
            print(f"  WARNING: failed to fetch {bm_unit}: {exc}")

        if i < len(to_fetch) - 1:
            time.sleep(PAUSE_SECONDS)

    if records:
        df_out = pd.DataFrame(records)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_out.to_parquet(OUTPUT_PATH, index=False)
        print(f"\nSaved {len(df_out)} records to {OUTPUT_PATH}")
    else:
        print("No records retrieved.")


if __name__ == "__main__":
    main()
