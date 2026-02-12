from astropy.nddata import CCDData
from skimage.registration import phase_cross_correlation
from skimage.transform import SimilarityTransform
import astroalign
from _utils import select_reference


class Register:
    """
    Encapsulates all factory functions for registration methods;
    all methods return a reference to a configured registration
    method, which allows user flexibility for method selection.
    """

    @staticmethod
    def build_triangulate() -> function:
        def triangulate(data: CCDData) -> list:
            """
            Estimates transformation from each
            data frame to a chosen reference image
            by matching 3-point asterisms
            between images. Uses astroalign's
            find_transform function

            :param data: contains image pixel-value
            data; must be 3D and is expected to be
            calibrated
            :type data: CCDData

            :return: contains 2D arrays
            encoding transformations from 
            image frames to a reference image;
            order corresponds to that of data.
            2D arrays are of shape(data[1]-1, data[1]-1)
            :rtype: list
            """
            # Select reference image based on
            # min distortion magnitude
            reference_image = select_reference(data)

            # Estiamate transform from each
            # frame to reference
            registration_matrices = []
            for frame in data:
                transform, mask = astroalign.find_transform(
                    reference_image, frame
                )
                registration_matrices.append(transform)

            return registration_matrices
        return triangulate

    @staticmethod
    def build_fourier_match() -> function:
        def fourier_match(data: CCDData) -> list:
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

            :return: contains 2D arrays
            encoding transformations from 
            image frames to a reference image;
            order corresponds to that of data.
            2D arrays are of shape(data[1]-1, data[1]-1)
            :rtype: CCDData
            """
            # Select reference image based on
            # min distortion magnitude
            reference_image = select_reference(data)

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
                trans_vec, _, _ = phase_cross_correlation(
                    reference_image, data)

                # Create transformation matrix for alignment
                transform = SimilarityTransform(
                    scale=scale,
                    rotation=rotation,
                    translation=trans_vec,
                    dimensionality=data.shape[1]-1
                )

                registration_matrices.append(transform)
                return registration_matrices
            return fourier_match

    @staticmethod
    def build_plate_solve() -> function:
        def plate_solve(data: CCDData) -> CCDData:
            pass
        return plate_solve
