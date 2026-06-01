from typing import Callable

from astropy.nddata import CCDData
from astropy import stats
import numpy as np


class Coaddition:
    """
    Encapsulates all factory functions for stacking methods;
    all methods return a reference to a configured stack
    method, which allows user flexibility for method selection.
    """

    @staticmethod
    def build_median() -> Callable:
        def median(data: np.ndarray) -> np.ndarray:
            # Use masked median to avoid outliers
            return np.ma.median(data, axis=0)
        return median

    @staticmethod
    def build_mean() -> Callable:
        def mean(data: np.ndarray) -> np.ndarray:
            # Use masked mean to avoid outliers
            return np.ma.mean(data, axis=0)
        return mean

    @staticmethod
    def build_ivw_mean(epsilon: float = 1.0) -> Callable:
        def iv_weighted_mean(data: np.ndarray) -> np.ndarray:
            """
            Inverse-variance weighted mean per pixel across the frame index.

            Each pixel is weighted by ``1 / variance``. The variance is estimated
            from the signal itself as a shot-noise proxy (Poisson: variance grows
            with signal), so brighter -- noisier -- samples are down-weighted. This
            needs no calibration side-inputs, fitting the cube-operator contract:
            it takes the (n_frames, ny, nx) cube and returns the (ny, nx) plane.

            :param data: the frame cube (axis 0 = frame index); may be masked.
            :type data: np.ndarray
            :param epsilon: variance floor added to every pixel, so faint/zero
                pixels get a finite (large but bounded) weight instead of dividing
                by zero.
            :type epsilon: float
            :return: 2D array of the weighted-mean stacked pixel values.
            :rtype: np.ndarray
            """
            # Shot-noise variance proxy: ~ signal, floored by epsilon and clamped
            # non-negative (calibration can push some pixels slightly below zero).
            variance = np.clip(np.ma.getdata(data), 0.0, None) + epsilon
            weights = 1.0 / variance
            return np.ma.average(data, axis=0, weights=weights)
        return iv_weighted_mean

    @staticmethod
    def build_biweight_mean(c: float) -> Callable:
        def biweight_mean(data: CCDData) -> CCDData:
            """
            Calculate the biweight mean 
            per pixel across frame index

            :param data: array-like containing image data;
            expected to be 3D and calibrated
            :type data: CCDData

            :param c: tuning constant for biweight estimator;
            should be chosen such that more extreme noise gets 
            a smaller c; typical values are 4.0-8.0
            :type c: float

            :return: 2D array of biweight-mean stacked pixel values
            :rtype: CCDData
            """
            return stats.biweight_location(data, axis=0, c=c, ignore_nan=True)
        return biweight_mean
