from astropy.io import fits
from pathlib import Path
import sys


def inspect_hdr(file_path):
    # Returns FITS primary header
    # for easy access throughout project
    file = Path(file_path)
    with fits.open(file) as hdul:
        hdr = hdul[0].header  # type: ignore[attr-defined]

    return hdr


# To easily run from terminal
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_fits.py <file.fits>")
        sys.exit(1)

    file_path = sys.argv[1]
    header = inspect_hdr(file_path)
    print(header)
