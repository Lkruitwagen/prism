# Unmixing BM data to individual assets

The purpose of this task is to assign remaining plants in @data/dukes_clean.csv, unmatched in @data/matches.csv, 
to 'supplier' bm units, which aggregate generation of small, embedded plants.

Lets estimate the electricity production of unmatched wind and solar estimates using sensible defaults for power curve parameters.
Then let's assign the production of each asset to a supplier BM Unit. 
We can treat this as a linear assignment problem - creating a bipartite graph between assets and supplier BM units, where each asset has an edge to only a single BM unit.
Our loss should be the sum of the residual BM unit generation, subtracting the allocated asset-level generation.

We can shard our problem using the grid supply points, which we have in @data/GSP_regions_4326_20250109_simplified.geojson.
Each bm unit only represents a single gris supply region.
So we can solve one mixed-integer linear problem (MILP) per grid supply region.

Let's use linopy as our framework for building our MILP.
We have the HiGHs solver installed already that we can use.
Create a new python module @prism/assignment.py to contain our MILP code.
Create a new entrypoint in out @prism/cli.py for launch the assignment problem.
The user should be able to choose which grid supply region to run, or should be able to specify 'all' to run them all in sequence.
Persist the asset-to-bmunit assignment in a json file.

Plan first and ask any clarification necessary.
Update clarifications on this document.
When your're done executing, update the @CLAUDE.md with anything you've learned.