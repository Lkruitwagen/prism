# Orchestration

We now have a full many-to-many assignment of GB energy plants (via dukes) to bm units.
We have our fit parameters for plants that were pre-matched, and we have assigned the remaining unmatched plants to bm units using a linear programme.
Now we want to orchestrate pulling bm unit data and weather data to see how our assignment is performing over time and how the residual is changing.

We want to set up a daily orchestration. Every day at midnight we want to:
- pull the bm unit data from the api for a given lag from the current day.
- load the era5 weather data from the public google bucket archive.
- use the weather data to estimate plant-level generation; using our best-fit parameters for matched plants, and our estimated parameters for unmatched plants.
- store bm unit quantities and plant-level generation estimates in a json blob that we can render in a ui in future work.
We'll store the json blob in a public google storage bucket.

Create a new cli entrypoint (@prism/cli.py) for inference.
The cli should accept a date, but should also default to <today> if no date is given.
We may want to refactor parts of scripts like @scripts/fetch_b1610_geneartion.py and @scripts/fetch_era5_uk.py so we can reuse code in a proper python module.
The orchestration should create the json blob and name it with `inference_<YYYY-MM-DD>.json`.
Finally let's create a github workflow that runs the orchestration as a daily cron job and copies the inference json to a google storage bucket.

Plan first and ask any clarification necessary.
Update clarifications on this document.
When your're done executing, update the @CLAUDE.md with anything you've learned.

## Clarifications (resolved)

1. **Fitted parameters** — use `data/fits-wind.json` and `data/fits-solar.json` (checked in to repo so available in GitHub runner).
2. **ERA5 strategy** — fetch one day at a time from the main zarr archive; use a 10-day default lag.
3. **JSON structure** — `{date, bm_unit_quantities: {unit_id: {period: MW}}, plant_generation: [...records]}`.
4. **GCS bucket** — read from `GCS_BUCKET` environment variable; GitHub workflow sets it from `vars.GCS_BUCKET`. Service account key in `secrets.GCP_SA_KEY`.
5. **Breakpoint in assignment.py** — left as-is.

## Implementation

- `prism/fetch.py` — `fetch_b1610_day`, `fetch_era5_day`
- `prism/inference.py` — `run_inference`
- `prism/cli.py` — `prism infer` command added
- `.github/workflows/daily_inference.yml` — cron `0 2 * * *`