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
    def build_ivw_mean(bias_data: CCDData) -> Callable:
        def iv_weighted_mean(light_data: CCDData) -> CCDData:
            """
            Calculates the inverse-variance weighted mean
            per pixel across the frame index

            :param light_data: array-like object containing light-frame iamge data; 
            must have a dict-like 'header' attribute with gain specified by 'egain';
            expected to be 3D, and already be calibrated
            :type light_data: CCDData

            :param bias_data: array-like object containing average bias-frame image data;
            expected to be 2D
            :type bias_data: CCDData

            :return: 2D array of IVWM stacked pixel values
            :rtype: CCDData[shape(<NAXIS1>, <NAXIS2>), dtype[<BITPIX>]]
            """
            # Access gain from FITS file header
            gain = light_data.header['egain']

            # Calc variance of light frames
            light_var = light_data * gain

            # Calc variance of bias frames
            read_var = np.ma.var(bias_data, axis=0) * gain**2

            # Calc total variance of image across frames
            total_var = light_var + read_var

            weights = 1 / total_var
            return np.ma.average(light_data, axis=0, weights=weights)
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
