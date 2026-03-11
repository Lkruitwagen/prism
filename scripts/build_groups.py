#!/usr/bin/env python3
"""Build groups.json: connected components of DUKES plants and BM units.

Joins two sources:
  - data/matches.csv      (manually matched DUKES sites → specific BM units)
  - data/assignment.json  (MILP-assigned unmatched DUKES plants → supplier BM units)

A "group" is a connected component in the bipartite graph between DUKES plant
indices and BM unit IDs.  Two DUKES plants end up in the same group if they
share at least one BM unit (e.g. Grain and Grain OCGT both use T_GRAI1G).

Output: data/groups.json with four keys:

  groups_to_bmunit:    {group_id: [bm_unit_id, ...]}
  groups_to_dukes_idx: {group_id: [dukes_idx, ...]}
  dukes_idx_to_group:  {dukes_idx: group_id}
  bm_unit_to_group:    {bm_unit_id: group_id}

Usage:
    uv run python scripts/build_groups.py [--data-dir data] [--output data/groups.json]
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Union-Find (path-compressed) for connected components
# ---------------------------------------------------------------------------


class UnionFind:
    def __init__(self):
        self._parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        if x not in self._parent:
            self._parent[x] = x
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra

    def components(self) -> dict[str, list[str]]:
        """Return {root: [members]} for every component."""
        groups: dict[str, list[str]] = defaultdict(list)
        for node in self._parent:
            groups[self.find(node)].append(node)
        return dict(groups)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Build groups.json from matches and assignment.")
    parser.add_argument("--data-dir", default="data", help="Root data directory")
    parser.add_argument("--output", default="data/groups.json", help="Output JSON path")
    args = parser.parse_args()

    data_path = Path(args.data_dir)
    output_path = Path(args.output)

    # --- Load sources ---
    dukes = pd.read_csv(data_path / "dukes_clean.csv")
    matches = pd.read_csv(data_path / "matches.csv", index_col=0)

    assignment_path = data_path / "assignment.json"
    if assignment_path.exists():
        assignment: dict[str, dict] = json.loads(assignment_path.read_text())
    else:
        assignment = {}
        print("Warning: assignment.json not found — building groups from matches.csv only.")

    # site_name → DUKES index (integer).  Each site appears at most once in DUKES.
    site_to_idx: dict[str, int] = {row["Site Name"]: int(idx) for idx, row in dukes.iterrows()}

    uf = UnionFind()

    # --- Edges from matches.csv ---
    missing_sites: list[str] = []
    for site_name, group_df in matches.groupby("dukes_site_name"):
        dukes_idx = site_to_idx.get(site_name)
        if dukes_idx is None:
            missing_sites.append(site_name)
            # Still register BM units without a DUKES node; they may later
            # merge with other components via shared BM units.
            bm_units = group_df["bm_unit_id"].tolist()
            for bmu in bm_units:
                uf.find(f"bmu:{bmu}")  # ensure node exists
            for i in range(1, len(bm_units)):
                uf.union(f"bmu:{bm_units[0]}", f"bmu:{bm_units[i]}")
            continue

        d_node = f"dukes:{dukes_idx}"
        for bm_unit_id in group_df["bm_unit_id"].tolist():
            uf.union(d_node, f"bmu:{bm_unit_id}")

    if missing_sites:
        print(f"Warning: {len(missing_sites)} site(s) in matches.csv not found in DUKES:")
        for s in missing_sites:
            print(f"  {s!r}")

    # --- Edges from assignment.json ---
    for dukes_idx_str, record in assignment.items():
        d_node = f"dukes:{dukes_idx_str}"
        uf.union(d_node, f"bmu:{record['bm_unit_id']}")

    # --- Extract connected components → groups ---
    raw_components = uf.components()

    # Sort groups: largest first (by number of members), then alphabetically
    sorted_roots = sorted(raw_components, key=lambda r: (-len(raw_components[r]), r))

    groups_to_bmunit: dict[str, list[str]] = {}
    groups_to_dukes_idx: dict[str, list[int]] = {}
    dukes_idx_to_group: dict[str, str] = {}
    bm_unit_to_group: dict[str, str] = {}

    for group_id, root in enumerate(sorted_roots):
        members = raw_components[root]
        gid = str(group_id)

        bm_units = sorted(m[4:] for m in members if m.startswith("bmu:"))
        dukes_indices = sorted(int(m[6:]) for m in members if m.startswith("dukes:"))

        groups_to_bmunit[gid] = bm_units
        groups_to_dukes_idx[gid] = dukes_indices

        for idx in dukes_indices:
            dukes_idx_to_group[str(idx)] = gid
        for bmu in bm_units:
            bm_unit_to_group[bmu] = gid

    output = {
        "groups_to_bmunit": groups_to_bmunit,
        "groups_to_dukes_idx": groups_to_dukes_idx,
        "dukes_idx_to_group": dukes_idx_to_group,
        "bm_unit_to_group": bm_unit_to_group,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))

    n_groups = len(groups_to_bmunit)
    n_dukes = len(dukes_idx_to_group)
    n_bmu = len(bm_unit_to_group)
    multi_dukes = sum(1 for v in groups_to_dukes_idx.values() if len(v) > 1)
    multi_bmu = sum(1 for v in groups_to_bmunit.values() if len(v) > 1)

    print(f"Saved {n_groups} groups to {output_path}")
    print(f"  {n_dukes} DUKES plants  |  {n_bmu} BM units")
    print(f"  {multi_dukes} groups with >1 DUKES plant  |  {multi_bmu} groups with >1 BM unit")


if __name__ == "__main__":
    main()
