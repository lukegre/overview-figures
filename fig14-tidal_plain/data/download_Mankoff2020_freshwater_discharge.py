import pathlib

import nest_asyncio
import nest_asyncio2

# easyDataverse calls nest_asyncio.apply() at import time, but nest_asyncio 1.6.0
# breaks anyio's task-state tracking on Python 3.14 (asyncio.current_task()
# returns None -> "cannot create weak reference to 'NoneType'" inside httpcore).
# nest_asyncio2 is the maintained fork; swap it in before easyDataverse imports.
nest_asyncio.apply = nest_asyncio2.apply

import dotenv
import easyDataverse as edv

BASE = pathlib.Path(dotenv.find_dotenv()).parent


def main():
    api_url = "https://dataverse.geus.dk/"
    dataverse = edv.Dataverse(api_url)

    filenames = [f"freshwater/land/discharge/MAR_{year}.nc" for year in range(1992, 2024)] + [
        "freshwater/land/outlets.gpkg"
    ]

    dataverse.load_dataset(
        pid="doi:10.22008/FK2/XKQVL7",
        filedir=str(BASE / "data/Mankoff2020/"),
        filenames=filenames,
        n_parallel_downloads=10,
        download_files=True,
    )


if __name__ == "__main__":
    main()
