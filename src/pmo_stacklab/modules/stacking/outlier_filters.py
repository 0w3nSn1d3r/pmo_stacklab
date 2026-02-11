from astropy.nddata import CCDData
from astropy import stats
from typing import Tuple
from scipy.stats import mstats
import numpy as np


class OutlierFilters:
    """
    Encapsulates all factory functions for outlier filter methods;
    all methods return a reference to a configured filter
    method, which allows user flexibility for method selection.
    """

    @staticmethod
    def build_sigma_clip(sigma: float) -> function:
        def sigma_clip(data: CCDData) -> CCDData:
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
        return sigma_clip

    @staticmethod
    def build_winsorize(limits: Tuple[float, float]) -> function:
        def winsorize(data: CCDData) -> CCDData:
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
        return winsorize

    @staticmethod
    def build_percentile_clip(limits: Tuple[float, float]) -> function:
        def percentile_clip(data: CCDData) -> CCDData:
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
        return percentile_clip
