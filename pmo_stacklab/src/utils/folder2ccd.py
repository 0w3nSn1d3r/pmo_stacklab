from astropy.nddata import CCDData
from pathlib import Path
import numpy as np


def parse_data_folder(folder: Path) -> dict:
    """
    Extracts FITS files from folders
    and converts them to CCDData objs;
    collects all frames by filter and then
    by type; allows for conversion to NDData
    objs to vectorize pipeline and propagate
    metadata like WCS.

    :param folder: path to folder containing frame types;
    must be structured with subfolders per type, and further
    subfolders per filter where applicable; ultimately contains
    .FITS files of image frames.
    :type folder: Path

    :return: contains filter- and type-collected frames;
    access via keys, 'lights', 'darks', 'biases', and 'flats'
    respectively. 
    :rtype: dict
    """

    # Folder contains subfolders per frame type
    subfolders = {}
    for subfolder in folder.iterdir():
        subfolders[f'{subfolder.stem}'] = subfolder

    light_folder = subfolder['light']
    dark_folder = subfolder['dark']
    bias_folder = subfolder['bias']
    flat_folder = subfolder['flat']

    # Lights contain subfolder per filter
    lights = np.array([])
    for filter_folder in light_folder.iterdir():
        files = filter_folder.iterdir()
        filter_frames = np.array(
            [CCDData.read(f, units='adu') for f in files]
        )

        # Lights depend on filter; contains arrays
        # of CCDData objs per frame per filter
        lights.append(filter_frames)

    # Doesn't depend on filter;
    # has no more subfolders
    darks = np.array([])
    for frame in dark_folder.iterdir():
        darks.append(CCDData.read(frame, units='adu'))

    # Doesn't depend on filter;
    # has no more subfolders
    biases = np.array([])
    for frame in bias_folder.iterdir():
        biases.append(CCDData.read(frame, units='adu'))

    flats = np.array([])
    for filter_folder in flat_folder.iterdir():
        files = filter_folder.iterdir()
        filter_frames = np.array(
            [CCDData.read(f, units='adu') for f in files]
        )

        # Flats depend on filter; contains arrays
        # of CCDData objs per frame per filter
        flats.append(filter_frames)

    return {'lights': lights,
            'darks': darks,
            'biases': biases,
            'flats': flats}
