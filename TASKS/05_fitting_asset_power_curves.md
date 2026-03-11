# Fitting asset-level power curves.

We are now prepared to fit power curves to observed data.
Let's fit some wind and solar supply curves to the plant-level data we matched to balancing mechanism actual generation data.

We have all the data we need:
- half-hourly physical settlement data: @data/b1610/*.parquet
- all balancing mechanism details: @data/missing_bm_units_details.parquet and @data/bm_unit_catalogue.parquet
- plant-level details @data/dukes_clean.csv
- matches between dukes and bm_units: @data/matches.csv
- a cube of meteorological data for Jan-Feb 2026: @data/era5_uk_2026_jan_feb.nc

Let's create canonical power curves for wind and solar.
The wind power curve should follow the weibull cumulative distribution function with wind speed as an input, with a cut-out speed.
The solar power curve should be a simple efficiency multiple of the incident downward solar radiation.
Let's define these power curves in Jax so we can use an autograd approach to fitting them.
One other complication: let's include the possibility that the generation is curtailed (i.e. forced to zero).

In our main @prism/ module, lets now create some python modules. 
Let's create solar.py, wind.py, fit.py, met.py, and bmdata.py.
solar.py and wind.py should include the formulae for the power curves.
fit.py should include the generic fitting approach, met.py can handle loading and sampling our met data cube, bmdata.py can handle and join our balancing data.
Let's also create a cli.py entrypoint. The user should be able to specify a bmunit to fit, and a timeframe over which to fit the data.

Once this is done, let's create a notebook where we can load the data for a bmunit, fit it, and visualise and explore the fit and residual error.

Plan first and ask any clarification necessary.
Update clarifications on this document.
When your're done executing, update the @CLAUDE.md with anything you've learned.