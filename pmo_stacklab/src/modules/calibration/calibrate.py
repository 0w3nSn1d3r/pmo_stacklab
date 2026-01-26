from ccdproc import combine, subtract_dark, subtract_bias, flat_correct
from astropy.nddata import CCDData, NDData
import numpy as np


class Calibrate:
    def calibrate(self,
                  lights: np.ndarray,
                  darks: np.ndarray,
                  biases: np.ndarray,
                  flats: np.ndarray) -> np.ndarray:
        """
        Docstring for calibrate

        :param self: Description

        :param lights: Description
        :type lights: NDData

        :param darks: Description
        :type darks: NDData

        :param biases: Description
        :type biases: NDData

        :param flats: Description
        :type flats: NDData

        :return: Description
        :rtype: NDData
        """

        # Create master frames with median
        master_dark = combine(darks, method='median', sigma_clip=True)
        master_bias = combine(biases, method='median', sigma_clip=True)
        master_flat = combine(flats, method='median', sigma_clip=True)
        # Normalize flat to not distort image
        master_flat /= master_flat.data.mean()

        # Convert light frames from CCDData list
        # to NumPy data cube -- shape: (n_frames, ny, nx)
        light_frames = np.array([ccd.data for ccd in lights])

        # Subtract bias (master_bias is 2D)
        light_frames -= master_bias.data

        # Subtract dark (scaled if exposures differ)
        scale_factors = np.array(
            [ccd.header['EXPTIME']/master_dark.header['EXPTIME'] for ccd in lights])
        light_frames -= (master_dark.data[np.newaxis, :, :]
                         * scale_factors[:, np.newaxis, np.newaxis])

        # divide by flat
        light_frames /= master_flat.data

        # Re-wrap into array of CCDData objs
        calibrated_frames = [
            CCDData(frame, unit=lights[0].unit, meta=lights[i].meta)
            for i, frame in enumerate(light_frames)
        ]

        return calibrated_frames
