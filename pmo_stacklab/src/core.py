from astropy.nddata import CCDData
from pathlib import Path


def gen_final_img(
        folder_path: Path,
        calibrate: Calibrate,
        register: Register,
        stack: Stack,
        post_process: PostProcess
) -> CCDData:
    """
    Docstring for gen_final_img

    :param folder_path: Description
    :type folder_path: Path

    :param calibrate: Description
    :type calibrate: Calibrate

    :param register: Description
    :type register: Register

    :param stack: Description
    :type stack: Stack

    :param post_process: Description
    :type post_process: PostProcess

    :return: Description
    :rtype: CCDData
    """
    return
