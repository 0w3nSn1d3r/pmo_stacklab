from typing import Callable

from astropy.nddata import CCDData
import numpy as np


class PostProcess:
    def __init__(
            self,
            background_modeling: Callable,
            color_map: Callable,
            stretch: Callable,
            intensity_scaling: Callable,
    ):
        self.background_modeling = background_modeling
        self.color_map = color_map
        self.stretch = stretch
        self.intensity_scaling = intensity_scaling

    # TO-DO
    def post_process(self, data: np.ndarray) -> CCDData:
        pass
