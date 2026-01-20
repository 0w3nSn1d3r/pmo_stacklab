from astropy.io import fits
from astropy.stats import sigma_clip, mad_std
import numpy as np
from pathlib import Path
from typing import Callable


def stack(hdul: fits.HDUList,
          outlier_rejection: Callable[[np.ndarray], np.ndarray],
          stack_method: Callable[[list], np.ndarray]) -> np.ndarray:
    """
    Stack calibrated and registered data from all images

    :param hdul: list of FITS HDUs 
    :type data_folder: HDUList

    :param outlier_rejection: outlier-rejection function applied to data
    :type outlier_rejection: function

    :param stack_method: stacking function applied to data
    :type stack_method: function

    :return: stacked pixel values for final image
    """

    inlying_data = []
    for hdu in hdul:
        data = hdu.data  # type: ignore
        inlying_i = outlier_rejection(data)

        inlying_data.append(inlying_i)

    stacked_data = stack_method(inlying_data)
    return stacked_data
