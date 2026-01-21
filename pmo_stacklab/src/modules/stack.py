from astropy.io import fits
from astropy import stats
from scipy.stats import mstats
import numpy as np
from pathlib import Path
from typing import Tuple
from astropy.nddata import CCDData


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

    # Outlier filtering methods

    @staticmethod
    def sigma_clip(data: CCDData, sigma: float) -> CCDData:
        """
        Iteratively mask all input data values
        outside of <sigma> standard deviations
        until data converges

        :param data: contains image data pixel values;
        expected to be 3D and calibrated
        :type data: CCDData

        :param sigma: number of standard deviations
        for both upper and lower clipping limit
        :type sigma: float

        :return: masked array of input data 
        where all clipped values are masked as True
        :rtype: ndarray[_AnyShape, dtype[Any]]
        """

        return stats.sigma_clip(data, axis=0, sigma=sigma, stdfunc='mad_std')

    @staticmethod
    def winsorize(data: CCDData, limits: Tuple[float, float]) -> CCDData:
        """
        Replace all values of given dataset
        outside specified percentile range with
        nearest percentile value; i.e. values
        lower than lowest percentile are set to
        the value of the lowest percentile

        :param data: contains image data pixel values;
        expected to be 3D and calibrated
        :type data: np.ndarray

        :param limits: contains boundary percentiles;
        expressed as float in [0, 1]
        :type limits: Tuple[float, float]

        :return: winsorized array of input values
        :rtype: CCDData[(shape<NAXIS1>, <NAXIS2>), dtype[<BITPIX>]]
        """

        return mstats.winsorize(data, axis=0, limits=limits, inplace=True, nan_policy='omit')

    @staticmethod
    def percentile_clip(data: CCDData, limits: Tuple[float, float]) -> CCDData:
        """
        Mask all values of given dataset
        outside the specified percentile range

        :param data: contains image pixel values;
        expected to be 3D and calibrated
        :type data: np.ndarray

        :param limits: contains upper and lower bound
        percentiles expressed as floats in [0, 100];
        limits[0] = <lower bound>,
        limits[1] = <upper bound>
        :type limits: Tuple[float, float]

        :return: masked array of input data
        where all values outside bounds are
        masked as True
        :rtype: ndarray[shape(<NAXIS1>, <NAXIS2>), dtype[<BITPIX>]]
        """

        # Unpack percentile values from limits
        lower_perc, upper_perc = limits

        # Calc data values at specified percentiles
        lower_bound, upper_bound = np.stats.percentile(
            data, [lower_perc, upper_perc], axis=0
        )

        # Mask all data outside percentile bounds
        masked_data = np.ma.masked_outside(data, lower_bound, upper_bound)
        return masked_data

    # Stacking methods

    @staticmethod
    def median(data: np.ndarray) -> np.ndarray:
        # Use masked median to avoid outliers
        return np.ma.median(data, axis=0)

    @staticmethod
    def mean(data: np.ndarray) -> np.ndarray:
        # Use masked mean to avoid outliers
        return np.ma.mean(data, axis=0)

    @staticmethod
    def iv_weighted_mean(light_data: CCDData, bias_data: CCDData) -> CCDData:
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

    @staticmethod
    def biweight_mean(data: CCDData, c: float) -> CCDData:
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

            # Don't filter if 'none' is specified
            if self.outlier_filter:
                inlying_i = self.outlier_filter(data)
                inlying_data.append(inlying_i)
            else:
                inlying_data.append(data)

        stacked_data = self.stack_method(inlying_data)
        return stacked_data
