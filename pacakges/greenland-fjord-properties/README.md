# Greenland Fjord Properties

![DOMAIN](https://img.shields.io/badge/DOMAIN-Greenland-e0bb38?style=for-the-badge)
![CLUSTER](https://img.shields.io/badge/CLUSTER-ATM,_BIO-28a745?style=for-the-badge)
![PEOPLE](https://img.shields.io/badge/PEOPLE-Loic,_Lisa,_Virginie-2861a7?style=for-the-badge)

<a href="https://os.zhdk.cloud.switch.ch/spi-greenfjord-public/greenland-frjod-props-w_pace/web_display_pace/index.html">Web page showing tabular data</a>

Tools and scripts for deriving per-fjord geospatial and environmental properties for Greenland fjords. Below is a screenshot of the output in map representation. The dataset is also available in summarized tabular format and full netCDF/zarr formats. 

<a href="https://os.zhdk.cloud.switch.ch/spi-greenfjord-public/greenland-frjod-props-w_pace/web_display_pace/fjord_polygons.html" title="click to go to map web page"><img src="output/img.png"></a>

The repository builds fjord-wise datasets by combining:
- fjord geometry and centerline binning,
- bathymetry,
- glacier fronts,
- freshwater discharge,
- sea ice,
- ocean color (chlorophyll, turbidity, SPM),
- fishing effort.


## What this repo contains

- Python package: `src/fjord_props/`
  - `FjordAggregator` for geometry-aware aggregation along fjord distance bins.
  - Data loaders and helpers for local files, S3/simplecache paths, and YAML catalogs.
- Pipeline scripts:
  - `scripts/process_fjords.py`: builds per-fjord outputs (NetCDF, map, plots, serialized aggregator).
  - `scripts/compute_fjord_stats.py`: computes tabular summary statistics from processed fjord outputs.
- Data prep scripts in `scripts/data/` for OSM, CMEMS, Mankoff discharge, fishing effort, and fjord names.
- Example notebooks in `notebooks/`.

## Installation

Requirements:
- Python `>=3.12`
- `uv` package manager

Install dependencies:

```bash
uv sync
```

For notebook/dev work:

```bash
uv sync --group dev
```

## Configuration

Runtime settings are loaded from environment variables and `.env` (see `src/fjord_props/core/config.py`).

Typical variables used by scripts:
- `LOG_LEVEL`
- `CACHE_DIR`
- `COPERNICUSMARINE_SERVICE_USERNAME`
- `COPERNICUSMARINE_SERVICE_PASSWORD`
- `GFW_API_ACCESS_TOKEN`
- `DATAVERSE_API_TOKEN`
- S3/fsspec values (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `FSSPEC_*`)

Data catalogs are configured in:
- `data/data.yaml` (local file paths)
- `data/data_s3.yaml` (S3/simplecache paths)

## Data Preparation

Most raw/processed paths referenced by the pipeline are defined in `data/data.yaml`. Use the scripts under `scripts/data/` to build missing processed inputs.

Common steps:

```bash
uv run python scripts/data/process_osm.py
uv run python scripts/data/download_Mankoff2020_freshwater_discharge.py
uv run python scripts/data/process_Mankoff2020_discharge.py
uv run python scripts/data/download_and_process_fishing_data.py
uv run python scripts/data/download_cmems_arctic_chl.py
uv run python scripts/data/download_cmems_dmi_arctic_ice.py
```

## Main Pipeline

Process all fjords:

```bash
uv run python scripts/process_fjords.py
```

Process one fjord:

```bash
uv run python scripts/process_fjords.py --fjord-id 42
```

Per-fjord outputs are written to:
- `output/fjord_<id>/fjord_aggregator.pkl_joblib`
- `output/fjord_<id>/fjord_data.nc`
- `output/fjord_<id>/fjord_data_monthly_clim.nc`
- `output/fjord_<id>/fjord_interactive_map.html`
- `output/fjord_<id>/fjord_monthly_clim.png`

## Summary Statistics

Run:

```bash
uv run python scripts/compute_fjord_stats.py
```

Output:
- `output/fjord_summary_stats.csv`

Note: `scripts/compute_fjord_stats.py` currently expects processed fjord folders under `output/fjord_data/fjord_<id>/...` via `FNAME_*_TEMPLATE`. If your files are in `output/fjord_<id>/...` (the default from `process_fjords.py`), update the templates in `scripts/compute_fjord_stats.py` before running.

## Quick Python API Example

```python
import fjord_props as fp

cat = fp.read_yaml_source("data/data.yaml", **fp.cfg.model_dump())
data = fp.load_greenland_data(cat)
```

Key exports are defined in `src/fjord_props/__init__.py`:
- `FjordAggregator`
- `load_greenland_data`
- `get_fjord_discharge`
- `get_catchment_glacier_fronts`
- `set_fjord_names`

## Project Layout

```text
src/fjord_props/         Python package
scripts/                 Main processing/stat scripts
scripts/data/            Data download and preprocessing scripts
data/                    YAML catalogs + raw/processed data roots
notebooks/               Exploration/development notebooks
output/                  Generated outputs
```
