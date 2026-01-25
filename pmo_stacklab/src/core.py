from astropy.nddata import CCDData
from pathlib import Path
from modules.calibration.calibrate import Calibrate
from modules.reprojection.reproject import Reproject
from modules.stacking.stack import Stack
from modules.post_processing.post_process import PostProcess
from pmo_stacklab.src.utils.folder2ccd import parse_data_folder


def calc_final_img(
        folder_path: Path,
        calibrater: Calibrate,
        reprojecter: Reproject,
        stacker: Stack,
        post_processer: PostProcess
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

    all_data = parse_data_folder(folder_path)
    lights = all_data['light']
    darks = all_data['dark']
    biases = all_data['bias']
    flats = all_data['flat']

    calibrated = calibrater.calibrate(lights, darks, biases, flats)
    reprojected = reprojecter.reproject(calibrated)
    stacked = stacker.stack(reprojected)
    final_img = post_processer.post_process(stacked)

    return final_img
