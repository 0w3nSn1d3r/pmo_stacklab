import os
from astropy.io import fits

# Main folder containing the two subfolders
main_folder = "C:/Astro data/calibration_frames"

# Mapping of calibration types to their exact IMAGETYP values
calibration_map = {
    "bias": ["bias frame"],
    "dark": ["dark frame"],
    "flat": ["flat field"]
}


def classify_calibration_frames(folder_path):
    bias_frames = []
    dark_frames = []
    flat_frames = []

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".fits"):
            file_path = os.path.join(folder_path, filename)
            with fits.open(file_path) as hdul:
                imagetyp = hdul[0].header.get("IMAGETYP", "")
                if imagetyp is None:
                    continue
                imagetyp_clean = imagetyp.strip().lower()

                if imagetyp_clean in calibration_map["bias"]:
                    bias_frames.append(filename)
                elif imagetyp_clean in calibration_map["dark"]:
                    dark_frames.append(filename)
                elif imagetyp_clean in calibration_map["flat"]:
                    flat_frames.append(filename)
    return bias_frames, dark_frames, flat_frames


# Process each subfolder
for subfolder in os.listdir(main_folder):
    subfolder_path = os.path.join(main_folder, subfolder)
    if os.path.isdir(subfolder_path):
        bias, dark, flat = classify_calibration_frames(subfolder_path)
        print(f"\nSubfolder: {subfolder}")
        print("Bias frames:", bias)
        print("Dark frames:", dark)
        print("Flat frames:", flat)
