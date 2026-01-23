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
            )

            registration_matrices.append(transform)

    @staticmethod
    def plate_solve(data: CCDData) -> CCDData:
        pass
