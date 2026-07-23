
def save_figures_to_pdf(fig_list, pdf_name, return_figures=False, **savefig_kwargs):
    """
    Saves a list of figure objects to a pdf with multiple pages.
    Parameters
    ----------
    fig_list : list
        list of figure objects
    pdf_name : str
        path to save pdf to.
    savefig_kwargs : key-value pairs passed to ``Figure.savefig``
    Returns
    -------
    None
    """
    import matplotlib.backends.backend_pdf
    from matplotlib import pyplot as plt

    pdf = matplotlib.backends.backend_pdf.PdfPages(pdf_name)

    kwargs = dict(dpi=120, bbox_inches='tight')
    kwargs.update(savefig_kwargs)

    for fig in fig_list:  # will open an empty extra figure :(
        pdf.savefig(fig, **kwargs)
    pdf.close()

    if return_figures:
        return fig_list
    else:
        plt.close("all")


def save_folium_as_image(map, filename):
    import io
    from PIL import Image

    img_data = map._to_png(5)
    img_rgba = Image.open(io.BytesIO(img_data))

    if filename.endswith('.png'):
        img_rgba.save(filename)
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        img_rgb = img_rgba.convert('RGB')
        img_rgb.save(filename)
    else:
        raise ValueError(f"Unsupported file format: {filename}. Currently only [png, jpg, jpeg] are supported.")
    

def doy_ticks_to_mon_abbrev(img)->None:
    """
    Converts a mappable objects day-of-year colorbar ticks to month abbreviations.
    For example, [15, 75, 135] would be converted to [Jan, Mar, May].

    Args:
        img (mappable): The mappable object with a colorbar.

    Returns:
        None (modifies the colorbar ticks in place)
    """
    import numpy as np

    def dayofyear_to_month_decimal(arr: np.ndarray) -> np.ndarray:
        return arr / 365 * 12

    def months_to_dayofyear(arr: np.ndarray) -> np.ndarray:
        return arr * 365 / 12

    # round up if the decimal part is greater than 0.5
    def round_half_up(x):
        return np.ceil(x) if x % 1 >= 0.5 else np.floor(x)

    # round down if the decimal part is less than 0.5
    def round_half_down(x):
        return np.floor(x) if x % 1 < 0.5 else np.ceil(x)

    import calendar as cal

    vmin, vmax = img.get_clim()
    months = dayofyear_to_month_decimal(np.array([vmin, vmax]))
    tmin = round_half_down(months[0])
    tmax = round_half_up(months[1]) + 1
    
    months = np.arange(tmin, tmax, dtype='int')
    doys = months_to_dayofyear(months)
    img.set_clim(doys[[0, -1]])

    labels = [cal.month_abbr[m] for m in months]
    ticks = months_to_dayofyear(months)

    img.colorbar.set_ticks(ticks)
    img.colorbar.set_ticklabels(labels)