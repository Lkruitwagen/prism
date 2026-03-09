# Data Collection

This task is to write the scripts necessary for our basic data collection. 
Three scripts should be written in @scripts/.
Any additional dependencies required should be added to the `pyproject.toml`.
Create a new section of the README for `scripts` and update it after script creation.
Also create a new section of the README called `Data Sources` and add each data source to an itemised list. 
I'll clean these up later.

Scripts will be prepared one at a time.
Plan first and ask any clarification necessary. 
Update clarifications on this document.
When your're done executing, update the @CLAUDE.md with anything you've learned.

## Script 1: BM Unit Catalogue

The first script should retrieve the entire BM Unit catalog from `https://data.elexon.co.uk/bmrs/api/v1/reference/bmunits/all`.
The output should be formatted to a dataframe and saved as a parquet file in @data/.

## Script 2: BM Unit Data

The second script should retrieve the actual generation output per generating unit.
This is the B1610 stream from the elexon API.
Prepare a script that allows the user to specify the start date and the end date.
The start date should be reformatted to iso-standard datetime, and the end-date should be reformatted to iso-standard datetime.
The request url is `https://data.elexon.co.uk/bmrs/api/v1/datasets/B1610/stream` and the params are: `{'to':<end_datetime_iso>,'from':<start_datetime_iso>}`.
The script should loop and retrieve one day's worth of data at a time, and reformat it from json to parquet.
Wait for 30s between API calls to not trigger a 429.

## Script 3: Reproject DUKES, backfill missing, and join to GSP regions.

Power plant data is available at @data/dukes_5_11.csv.
This data has x-coordinate and y-coordinate geospatial coordinates that need to be converted from EPSG 27700 to EPSG 4326.
Some of the data is missing lat and lon coordinates, they have been added in @data/extra_locations.csv.
Fill in this missing data.
Finally, we want to spatially join our Grid Supply Point (GSP) data onto this plant data.
We have the Grid Supply Point map from NESO @data/GSP_regions_4326_20250109.geojson.
We will want to first dissolve this data to the `GSPGroup`. 
Dissolve the geodataframe and then spatially join the GSPGroup onto the dukes data.
Save the cleaned and joined DUKES data as @data/dukes_clean.csv.