from astropy.io import fits
from astropy import stats
from scipy.stats import mstats
import numpy as np
from pathlib import Path
from typing import Callable


class Stack:
    def __init__(self, outlier_filter, stacking_method):
        # Prevent case-sensitive errors
        outlier_filter = outlier_filter.lower()

        # Assign specified outlier filtering and stacking methods;
        # allows for customizable stacking process
        match outlier_filter:
            case 'sigma_clip':
                self.outlier_filter = self.sigma_clip
            case 'winsorize':
                self.outlier_filter = self.winsorize
            case 'percentile_clip':
                self.outlier_filter = self.percentile_clip
            case 'none':
                self.outlier_filter = None

        match stacking_method:
            case 'median':
                self.stacking_method = self.median
            case 'mean':
                self.stacking_method = self.mean
            case 'iv_weighted_mean':
                self.stacking_method = self.iv_weighted_mean
            case 'biweight_mean':
                self.stacking_method = self.biweight_mean

    def stack_data(self, data: fits.HDUList) -> np.ndarray:
        """
        Coordinate functions in the stacking process
        to stack calibrated and registered data from all images.

        :param data: list of FITS HDUs 
        :type data: HDUList

        :return: stacked pixel values for final image
        """
        inlying_data = []
        for hdu in data:
            data = hdu.data  # type: ignore
            inlying_i = self.outlier_filter(data)

            inlying_data.append(inlying_i)

        stacked_data = self.stack_method(inlying_data)
        return stacked_data
