"""
DMI Meteorological Observation API (metObs v2) — no API key required.
Docs: https://www.dmi.dk/friedata/dokumentation/meteorological-observation-api

Data are raw (not quality controlled). Narsarsuaq (04270) is hourly from ~2000,
3-hourly before that.
"""

API_URL = 'https://opendataapi.dmi.dk/v2/metObs/collections/observation/items'
NARSARSUAQ = '04270'

# API parameterId -> column name (names kept from the DMIRep24-08 csv files)
parameter_dict = {
    "temp_dry": "mean_air_temp",
    "temp_max_past1h": "abs_max_temp_last_hour",
    "temp_max_past12h": "abs_max_temp_last_12_hours",
    "temp_min_past1h": "abs_min_temp_last_hour",
    "temp_min_past12h": "abs_min_temp_last_12_hours",
    "humidity": "mean_rel_humidity",
    "wind_speed": "mean_wind_speed",
    "wind_gust_always_past1h": "highest_wind_speed_last_hour",
    "wind_dir": "mean_wind_direction",
    "wind_dir_past1h": "mean_wind_direction_last_hour",
    "pressure_at_sea": "air_pressure_sea_level",
    "precip_past1h": "accum_precip_last_hour",
    "cloud_cover": "cloud_cover_percent",
}


def fetch_dmi_parameter(station_id, parameter_id, start=None, end=None):
    """Fetch one parameter for a station as a time-indexed Series."""
    import requests
    import pandas as pd

    start = '..' if start is None else pd.Timestamp(start).strftime('%Y-%m-%dT%H:%M:%SZ')
    end = '..' if end is None else pd.Timestamp(end).strftime('%Y-%m-%dT%H:%M:%SZ')
    params = dict(
        stationId=station_id,
        parameterId=parameter_id,
        datetime=f'{start}/{end}',
        limit=300000,
    )

    records = []
    url = API_URL
    while url:
        r = requests.get(url, params=params, timeout=120)
        r.raise_for_status()
        data = r.json()
        records += [f['properties'] for f in data['features']]
        # follow pagination; the next link already contains the query
        url = next((ln['href'] for ln in data['links'] if ln['rel'] == 'next'), None)
        params = None
        if data['numberReturned'] == 0:
            break

    if not records:
        return pd.Series(dtype=float, name=parameter_id)

    df = pd.DataFrame(records)
    time = pd.to_datetime(df['observed']).dt.tz_localize(None)
    return pd.Series(df['value'].values, index=time, name=parameter_id).sort_index()


def fetch_dmi_station(station_id=NARSARSUAQ, start=None, end=None, parameters=parameter_dict):
    """
    Fetch hourly observations for a DMI station (default: Narsarsuaq).

    Parameters
    ----------
    station_id : str
        5-digit DMI station id (zero padded), e.g. '04270'
    start, end : str or datetime, optional
        Time range (UTC). None means open ended (full record / up to now)
    parameters : dict
        API parameterId -> output column name

    Returns
    -------
    pd.DataFrame indexed by hourly time (UTC, tz-naive)
    """
    import pandas as pd

    series = {
        name: fetch_dmi_parameter(station_id, pid, start, end)
        for pid, name in parameters.items()
    }
    df = pd.DataFrame(series)
    df.index.name = 'time'

    # -0.1 is DMI's code for trace precipitation (<0.1 mm)
    if 'accum_precip_last_hour' in df:
        df['accum_precip_last_hour'] = df['accum_precip_last_hour'].clip(lower=0)
    # 112 = sky obscured (fog/snow), not a cover percentage
    if 'cloud_cover_percent' in df:
        df['cloud_cover_percent'] = df['cloud_cover_percent'].where(lambda x: x <= 100)

    df = df.resample('1h').mean()

    return df


def download_dmi_data(station_id=NARSARSUAQ, dest_dir='../data/', start=None, end=None):
    """Fetch station data from the API and save to csv; returns the file path."""
    import pathlib

    df = fetch_dmi_station(station_id, start=start, end=end)

    dest_dir = pathlib.Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    t0, t1 = df.index[[0, -1]].strftime('%Y%m%d')
    fname = dest_dir / f'dmi_metobs-{station_id}-{t0}_{t1}.csv'
    df.to_csv(fname)

    return fname


def read_dmi_csv(fname):
    import pandas as pd

    return pd.read_csv(fname, index_col='time', parse_dates=['time'])
