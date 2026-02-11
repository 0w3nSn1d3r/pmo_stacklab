from astropy.nddata import CCDData
from pathlib import Path
from modules.calibration import Calibrate
from modules.reprojection import Reproject
from modules.stacking import Stack
from modules.post_processing import PostProcess
from _utils import folder2ccd


def calc_img(
        folder_path: Path,
        calibrater: Calibrate,
        reprojecter: Reproject,
        stacker: Stack,
        post_processer: PostProcess
) -> CCDData:
    """
    Extracts data from folder using parse_data_folder(folder_path)
    then applies complete configured stacking pipeline
    to produce the final image

    :param folder_path: path to structured folder
    containing all data; must be of GUI-generated
    structure, with subfolders per type and filter
    :type folder_path: Path

    :param calibrater: instance of Calibrate class
    with configured calibration methods passed;
    calibrate() method is applied to data
    :type calibrate: Calibrate

    :param reprojecter: instance of Reproject class
    with configured reprojection methods passed;
    reproject() method is applied to data
    :type reproject: Register

    :param stacker: instance of Stack class
    with configured stacking methods passed;
    stack() method is applied to data
    :type stack: Stack

    :param post_processer: instance of PostProcess class
    with configured post-processing methods passed;
    post_process() method is applied to data
    :type post_process: PostProcess

    :return: contains image pixel-value data
    for complete calibrated, reprojected, stacked,
    and post-processed image; also contains
    relevant metadata, such as WCS and units
    :rtype: CCDData
    """

    # Extract CCDData from folder
    all_data = folder2ccd(folder_path)
    lights = all_data['lights']
    darks = all_data['darks']
    biases = all_data['biases']
    flats = all_data['flats']

    # Apply stacking pipeline
    calibrated = calibrater.calibrate(lights, darks, biases, flats)
    reprojected = reprojecter.reproject(calibrated)
    stacked = stacker.stack(reprojected)
    final_img = post_processer.post_process(stacked)

    return final_img
