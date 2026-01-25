from astropy.io import fits
from astropy.nddata import CCDData
import numpy as np


class Stack:
    def __init__(self, outlier_filter: function, stack_method: function):
        # Assign specified outlier filtering and stacking methods;
        # allows for customizable stacking process

        self.outlier_filter = outlier_filter
        self.stack_method = stack_method

    def stack_data(self, data: fits.HDUList) -> CCDData:
        """
        Coordinate functions in the stacking process
        to stack calibrated and registered data from all images.

        :param data: list of FITS HDUs 
        :type data: HDUList

        :return: stacked pixel values for final image
        :rtype: CCDData
        """

        inlying_data = np.array([])
        for hdu in data:
            data = hdu.data

            # Don't filter if 'none' is specified
            if self.outlier_filter:
                inlying_i = self.outlier_filter(data)
                inlying_data.append(inlying_i)
            else:
                inlying_data.append(data)

        stacked_data = self.stack_method(inlying_data)
        return stacked_data
