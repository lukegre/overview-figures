import matplotlib.pyplot as plt

plt.rcParams['axes.titlelocation'] = 'left'


from .geo import (
    plot_map, 
    add_coastline, 
    GOOGLE_SATELLITE, 
    GOOGLE_TERRAIN)

from .utils import (
    save_figures_to_pdf,
    save_folium_as_image,
)