from astropy.io import fits
from pathlib import Path


def inspect(file_path):
    file = Path(file_path)
    with fits.open(file) as hdul:
        hdr = hdul[0].header

    print(repr(hdr))
