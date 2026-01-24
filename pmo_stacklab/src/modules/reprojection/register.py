from astropy.nddata import CCDData
from skimage import transform
from skimage.registration import phase_cross_correlation
import numpy as np
from utils import calc_reference_img


class Register:
    @staticmethod
    def triangulate(data: CCDData) -> CCDData:
        pass

    @staticmethod
    def feature_match(data: CCDData) -> CCDData:
        pass

    @staticmethod
    def fourier_match(data: CCDData) -> CCDData:
        """
        Estimate the transformation matrix
        from each frame to a chosen standard
        reference image; reference is chosen
        based to have least distortion according to
        coefficients in FITS header; transformation
        is estimated using both log-polar
        and linear Fourier phase correlation

        :param data: contains image pixel value data;
        must be 3D and is expected to be calibrated
        :type data: CCDData

        :return: list of transformation matrices
        ordered the same as input frames;
        shape is (data.shape[1] - 1, data.shape[1] - 1)
        :rtype: CCDData
        """

        # Select reference image based on lowest
        # magnitude distortion vector
        reference_image = calc_reference_img(data)

        registration_matrices = []
        for frame in data:
            center_x = frame.header['crpix1']
            center_y = frame.header['crpix2']

            logpolar_data = transform.warp_polar(
                data,
                channel_axis=0,
                center=(center_y, center_x),
                scaling='log'
            )

            # Rotation and scaling values
            trans_vec0, _, _ = phase_cross_correlation(
                reference_image, logpolar_data)
            rotation, scale = trans_vec0

            # Translation vector
            trans_vec, _, _ = phase_cross_correlation(reference_image, data)

            # Create transformation matrix for alignment
            transform = transform.SimilarityTransform(
                scale=scale,
                rotation=rotation,
                translation=trans_vec
                dimensionality=data.shape[1]-1
            )

            registration_matrices.append(transform)

    @staticmethod
    def plate_solve(data: CCDData) -> CCDData:
        pass
