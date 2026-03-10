# Matching plants to BM Units

This task is to build an interactive matching interface to match the power stations in @data/dukes_clean.csv 
to balancing mechanism units in @data/bm_unit_catalogue.parquet and @data/missing_bm_unit_details.parquet.
The interface should iterate through power stations in DUKES and propose prospective BM unit matches.
Matches should be one-to-many (one power stations to multiple bm units).
Not all power stations will have bm units.

The interface should be a simple command line utility that should be easy to look at and use. 
Propose a number of matches to the user and allow the user to specify which matches are valid, e.g. '1,2,5'.
Matching should be proposed based on the partial levenstein distance between the fields of the bm unit record and the fields of the DUKES plants.
We also want to be able to compare generating capacity, so include the generating capacity from DUKES and the generating capacity from the bm unit record.
We also want to join the max and min _observed_ quantity from the data in @data/b1610/*.parquet.

Prepare the interface as a script that can be run in @scripts. 
I recommend using nice interface tools like Rich.
Persist the results continuously so the script can be stopped and restarted.
Run the matching in order of DUKES generating capacity, starting with the largest capacity.


Plan first and ask any clarification necessary.
Update clarifications on this document.
When your're done executing, update the @CLAUDE.md with anything you've learned.

## Implementation notes

**Script:** `scripts/match_dukes_to_bm_units.py`
**Output:** `data/matches.json` — keys are DUKES row index (sorted by capacity desc), values are `{site_name, bm_units: [...elexonBmUnit...]}`.

### Matching field decision
- Initial composite-string approach (site name + company + elexonBmUnit + ngcBmUnit) produced poor matches.
- Narrowed to matching `Site Name` against `bmUnitName` only — still poor (bmUnitName is often a terse code).
- **Final approach:** match `Site Name` against the human-readable name parsed from `data/netalist.html`.
  - Each `<option>` in netalist has the form `<GSP Group> - <Station Name> (<BM_UNIT_ID>)`.
  - Strip the GSP group prefix → clean station name (e.g. "Drax", "Drax AGT").
  - 11,047 names parsed; 4,071/4,072 BM units covered.
  - Falls back to `bmUnitName` for the one unit with no NETA entry.
  - This gives correct top scores (e.g. Drax Power Station → T_DRAXX-1…6 all score 100).

### Observed quantity units
- B1610 `quantity` column is **MWh per half-hour**, not MW.
- Display values are multiplied by 2 to convert to MW for comparison against installed capacity.