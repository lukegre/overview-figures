# Fig. X — 2024 ocean transects

`plot_ocean_transects.py` turns the supplied 2024 CTD and nutrient data into
matched distance–depth sections for the land and glacial fjords. Every visual,
data-processing, interpolation, bathymetry, and output setting is in
`config.yaml`.

## What changed from the example

- Distance from the innermost station replaces longitude, so the two fjords
  read in the same direction and spatial patterns are easier to compare. Each
  x-axis spans the exact minimum and maximum station distances in that fjord.
- Each section uses a shared-x split depth scale: 0–50 m occupies the upper
  third and deeper water the lower two-thirds. Subtle break marks make the
  change in vertical scale explicit without obscuring the data.
- Potential temperature, salinity, nitrate + nitrite, and chlorophyll
  fluorescence are shown with one shared colour scale per variable.
- The densely sampled temperature and salinity fields use smooth Clough–Tocher
  piecewise-cubic interpolation within the measured distance–depth convex hull,
  constrained to each section's observed value range. Sparse nitrate and
  fluorescence fields retain linear interpolation to avoid cubic overshoot.
  Below the deepest constrained value at each distance, that value is held
  constant down to the seabed; no horizontal extrapolation is applied. Methods
  can be selected globally or per variable in the configuration.
- Nutrient sample locations are shown because nutrients were measured only at
  selected bottle depths.
- Station positions and cast extents are visible without heavy grid lines.
- Bathymetry matches the biodiversity figure: cached BedMachine v6 sections
  for fjord 56 (land) and 54 (glacial), using the deepest cell per cross-fjord
  polygon and a centred 2 km rolling mean. Profiles are independent of sample
  depths and x-limits. Cache files live in `../fig13-biodiversity/data/`.
- Bathymetry retains its distance-from-glacier coordinates; hydrographic data
  retain their workbook distance-from-innermost-station coordinates.

## Fluorescence choice

The fluorescence sensor was not calibrated, so the figure reports relative
instrument units rather than chlorophyll-a concentration. The Idronaut `Chla`
channel is used because it occurs in both fjords. The Seabird
`Fluorescence_ECO_AFL_FL` channel has a different baseline and scale and is not
merged with it. This avoids creating a false cross-instrument comparison.

## Run

### Inverse-distance weighting

Set `grid.method: idw` (or a variable's `interpolation_method: idw`) to use
anisotropic inverse-distance weighting. Existing per-variable method overrides
take precedence over the global method. The current cubic/linear defaults are
retained. Each variable may also supply an `idw` mapping to override grid settings.

The elliptical distance is `r = sqrt((dx / distance_scale_km)^2 +
(dz / depth_scale_m)^2)` and weights are proportional to `r ** (-power)`.
The default power is 2, using the nearest 32 observations in this scaled space.
Exact observation locations reproduce their values (duplicates are averaged).
IDW stays within the input value range without clipping. Local neighbor selection
can introduce small discontinuities when the neighbor set changes.

Both scales default to `auto`: horizontal scale is the mean gap between unique
sampled station distances; vertical scale is the mean of each profile's mean
gap between valid sampled depths. Estimates use the filtered, non-missing data
for each variable and fjord, so bottle samples get different scales from CTD
profiles. These are sampling-density heuristics, not fitted correlation lengths.
With distances measured in km and depths in m, these scales produce a physically
much wider horizontal kernel. Set numeric scales to choose its aspect ratio,
for example `distance_scale_km: 10` and `depth_scale_m: 5`. Multiplying both
scales by the same factor does not change normalized IDW weights or neighbors.

With `extrapolate: false`, IDW preserves the measured convex-hull mask before
the existing smoothing and bottom hold. With `true`, IDW also fills outside
the hull using the same anisotropic weights.

### Generate the figure

```bash
MPLCONFIGDIR="$TMPDIR/matplotlib" uv run --project .. python plot_ocean_transects.py
```

Pass another YAML file as the first argument to test alternate choices. The
default outputs are `figX-ocean-transects.png` and `figX-ocean-transects.pdf`.
Choose the cross-fjord bathymetry aggregation with `bathymetry.agg_method` in
the YAML (`min`, `median`, `mean`, or `max`), or override it for one run:

```bash
MPLCONFIGDIR="$TMPDIR/matplotlib" uv run --project .. python plot_ocean_transects.py \
  --bathymetry-aggregation median
```

The corresponding `bathymetry_<method>_fjord_<number>.nc` cache files must be
present in `../fig13-biodiversity/data/`.

## Suggested caption

**Figure X. Physical, chemical, and biological structure along the GreenFjord
2024 transects.** Potential temperature, salinity, nitrate + nitrite, and
chlorophyll fluorescence are shown for the land fjord (left) and glacial fjord
(right). Distance increases seaward from the innermost sampled station. Filled
circles mark CTD stations, vertical lines show cast extent, and dots in panels
(e–f) show bottle-sample locations. Temperature and salinity use smooth
Clough–Tocher piecewise-cubic interpolation within the sampled distance–depth
domain; sparse nitrate and fluorescence use linear interpolation. Below the
deepest constrained value at each distance, that value is held constant to the
seabed. Light grey indicates
BedMachine v6 bathymetry using the deepest cell per cross-fjord polygon and a
centred 2 km rolling mean, matching the biodiversity transects independently
of sampling depth.
