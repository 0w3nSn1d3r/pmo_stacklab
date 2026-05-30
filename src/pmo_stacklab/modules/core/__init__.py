"""Core pipeline infrastructure.

Houses the building blocks shared across all processes: the :class:`ImageData`
container threaded through the pipeline, and its :class:`MetadataPolicy`. Kept
deliberately light to import (only astropy), so depending on the core container
does not drag in the heavy per-process science modules.

(The legacy ``calc_img`` hard-coded pipeline still lives in this package and can
be imported directly from :mod:`pmo_stacklab.modules.core.calc_img`; it is no
longer re-exported here because it pulls in the full scientific stack and will
be superseded by the generalized endpoint.)
"""
from .image_data import ImageData
from .metadata_policy import MetadataPolicy
from .process import Operator, Process, sequential

__all__ = ["ImageData", "MetadataPolicy", "Operator", "Process", "sequential"]
