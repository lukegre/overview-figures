parameter_dict = {
    "101": "mean_air_temp",
    "112": "abs_max_temp_last_hour",
    "113": "abs_max_temp_last_12_hours",
    "122": "abs_min_temp_last_hour",
    "123": "abs_min_temp_last_12_hours",
    "201": "mean_rel_humidity",
    "301": "mean_wind_speed",
    "305": "highest_wind_speed_last_hour",
    "365": "mean_wind_direction",
    "371": "mean_wind_direction_last_hour",
    "401": "air_pressure_sea_level",
    "504": "accum_sunshine_duration",
    "550": "mean_inc_global_radiation",
    "601": "accum_precip_last_hour",
    "603": "accum_precip_last_12_hours",
    "609": "accum_precip_last_24_hours",
    "801": "cloud_cover_percent",
}


def download_dmi_data(dest_dir='../data/'):
    import requests
    import zipfile
    import pathlib
    import io

    url = 'https://www.dmi.dk/fileadmin/Rapporter/2024/DMIRep24-08_1958_2023_data1.zip'
    fname = pathlib.Path(url).stem
    dest_dir = pathlib.Path(dest_dir)
    dest_path = dest_dir / fname

    if not dest_path.exists():
        r = requests.get(url)

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(dest_dir)

    flist = list(dest_path.glob('*'))

    return flist


def read_dmi_csv(fname):
    import pandas as pd

    df = pd.read_csv(fname, sep=';').rename(columns=parameter_dict)

    # renmae variables to lower case, and no special characters [{}()[]etc] or spaces
    df.columns = (
        df.columns
        .str.lower()
        .str.replace('[^a-z0-9]', '_', regex=True)
        .str.strip('_'))

    # convert to datetime
    year = df['year'].astype(str)
    month = df['month'].astype(str).str.zfill(2)
    day = df['day'].astype(str).str.zfill(2)
    hour = df['hour_utc'].astype(str).str.zfill(2)
    df['time'] = pd.to_datetime(year + month + day + hour, format='%Y%m%d%H')

    drop_cols = ['year', 'month', 'day', 'hour_utc', 'station']
    df = df.set_index('time').drop(columns=drop_cols)
    df = df.resample('1h').interpolate()

    return df