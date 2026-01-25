from astropy.nddata import CCDData
import numpy as np
import re


def select_reference(data: CCDData) -> CCDData:
    """
    Selects a reference image with
    minimum distortion magnitude,
    calculated as norm of distortion
    coefficients; used for registration

    :param data: contains image pixel-values;
    must be 3D and is expected to be calibrated
    :type data: CCDData

    :return: frame with minimum distortion
    magnitude
    :rtype: CCDData
    """

    # Matches all distortion coefficient
    # FITS header keys
    dist_coefficient_pattern = re.compile(r'tr\d_\d')

    # Get distortion vectors from header
    dist_vecs = np.array([])
    for frame in data:
        hdr = frame.header

        # Get all distortion coefficients
        # per frame
        dist_co_names = re.findall(dist_coefficient_pattern, hdr.keys())

        dist_vec = np.array([])
        for name in dist_co_names:
            dist_vec.append(hdr[name])
        dist_vecs.append(dist_vec)

    # Take norm of each dist_vec (rows of dist_vecs)
    dist_mags = np.norm(dist_vecs, axis=1)

    # Mag index corresponds to frame
    min_mag = min(dist_mags)
    min_mag_index = dist_mags.index(min_mag)

    reference_image = data[min_mag_index]
    return reference_image
