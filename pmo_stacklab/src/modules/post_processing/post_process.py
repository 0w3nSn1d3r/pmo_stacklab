from astropy.nddata import CCDData
import numpy as np


class PostProcess:
    def __init__(
            self,
            background_modeling: function,
            color_map: function,
            stretch: function,
            intensity_scaling: function,
            channel_combination: function
    ):
        self.background_modeling = background_modeling
        self.color_map = color_map
        self.stretch = stretch
        self.intensity_scaling = intensity_scaling
        self.channel_combination = channel_combination

    # TO-DO
    def post_process(self, data: np.ndarray) -> CCDData:
        pass
