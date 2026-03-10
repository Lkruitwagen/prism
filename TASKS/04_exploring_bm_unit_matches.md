# Exploring BM Unit Matches

We now have all the data we need to start exploring our physical balancing mechanism data.
We have two months of daily volumes @data/b1610/*.parquet, 
we have our cleaned DUKES data @data/dukes_clean,
we have our BM unit details, @data/bm_unit_catalogue.parquet and @data/missing_bm_unit_details.parquet,
we have the matches between our BM units and our DUKES sites @data/matches.csv.

Let's create a jupyter notebook to explore our BM Unit data.
The notebook should load and manipulate our data and then present the following plots:
- a scatter map of DUKES units. The plants should be colored by their technology, with larger dots for larger plants. Plants that have been matched to BM Units should be filled, where they haven't been matched they should be hollow.
- a mekko barplot with DUKES units where the y-axis is the capacity of each plant, and the x-axis is the accumulated total capacity. Plants should be colored by their technology, and matched plants should be filled, unmatched plants should be hollow. This will show the long tail of unmatched renewable plants.
- daily BM volume stacked area plot by bm unit type. If BM units have matches, unmix them into separate series, by technology type (e.g. `T_matched_CCGT`, `T_unmatched`)

Use the following colors:
  - bioenergy: brown
  - nuclear: purple
  - hydro: blue
  - pumped-hydro: cyan
  - solar: yellow
  - wind: green
  - fossil-fuel/CCGT: black
  - OCGT: grey

Include a legend for each plot.

Prepare this as notebook in @notebooks/.
Plan first and ask any clarification necessary.
Update clarifications on this document.
When your're done executing, update the @CLAUDE.md with anything you've learned.