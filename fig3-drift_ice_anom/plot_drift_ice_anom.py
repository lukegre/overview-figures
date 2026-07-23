from pathlib import Path
from string import ascii_lowercase

import copernicusmarine as cm
import dotenv
from greenfjord.viz import geo

HERE = Path(__file__).parent.resolve()
REPO = Path(dotenv.find_dotenv("pyproject.toml")).parent.resolve()

seaice = cm.open_dataset(
    # dataset_id="METOFFICE-GLO-SST-L4-REP-OBS-SST",
    dataset_id="cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m",
    variables=["sea_ice_fraction"],
    minimum_longitude=-54.321030903535565,
    maximum_longitude=-35.788867378825024,
    minimum_latitude=57.245238862882346,
    maximum_latitude=67.53331493726209,
    start_datetime="2012-12-31T00:00:00",
    end_datetime="2025-12-31T00:00:00",
)


da = seaice.sea_ice_fraction > 0.05

mask_icecover = da.sum("time").compute().pipe(lambda x: x > 50)

days_per_year = da.sel(time=slice("2014", "2025")).groupby("time.year").sum("time").compute()
avg = days_per_year.mean("year")
anom = (days_per_year - avg).where(mask_icecover)


fg = anom.sel(latitude=slice(58.6, 63), longitude=slice(-52, -40)).pipe(
    geo.plot_map_subplots,
    plot_type="contourf",
    col="year",
    col_wrap=4,
    levels=11,
    extend="both",
    robust=True,
    aspect=1.1,
    figsize=(9, 5),
    land_color="0.93",
    cbar_kwargs={"extend": "both"},
)

fg.fig.subplots_adjust(hspace=0.1, wspace=0.1, right=0.83)
fg.cbar.set_label("Sea ice cover duration anomaly (days)", labelpad=10)

for i, ax in enumerate(fg.axs.flat):
    title = f"– {ax.get_title(loc='left')}"
    ax.set_title(title, loc="center", y=-0.02, x=0.12, ha="left", va="bottom", size="medium")
    ax.set_title(
        ascii_lowercase[i],
        loc="left",
        y=-0.02,
        x=0.04,
        va="bottom",
        size="medium",
        fontweight="bold",
    )

fg.fig.savefig(HERE / "fig3-drift_ice_anom-DMIOI.png", dpi=300, bbox_inches="tight")
