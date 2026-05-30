"""Core pipeline infrastructure.

Houses the building blocks shared across all processes: the generic
:class:`Process` class, the :class:`ImageData` container threaded through the
pipeline, and its :class:`MetadataPolicy`. Kept deliberately light to import
(only astropy), so depending on core does not drag in the heavy per-process
science modules.
"""
from .image_data import ImageData
from .metadata_policy import MetadataPolicy
from .process import Operator, Process, sequential

__all__ = ["ImageData", "MetadataPolicy", "Operator", "Process", "sequential"]
