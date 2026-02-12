import numpy as np


class Align:
    """
    Encapsulates all factory functions for alignment methods;
    all methods return a reference to a configured alignment
    method, which allows user flexibility for method selection.
    """

    def build_neighbor():
        def neighbor(frames: np.ndarray) -> np.ndarray:
            return
        return neighbor

    def build_bicubic():
        def bicubic(frames: np.ndarray) -> np.ndarray:
            return
        return bicubic

    def build_lanczos():
        def lanczos(frames: np.ndarray) -> np.ndarray:
            return
        return lanczos

    def build_exact():
        def exact(frames: np.ndarray) -> np.ndarray:
            return
        return exact
