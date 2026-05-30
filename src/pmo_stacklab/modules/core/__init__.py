"""Core pipeline infrastructure.

Houses the building blocks shared across all processes: the generic
:class:`Process` class and its declarative :class:`ProcessSpec`, the
:class:`ImageData` container threaded through the pipeline, its
:class:`MetadataPolicy`, and the generalized algorithm builder
(:class:`Algorithm` / :class:`Subprocess` plus the typed :class:`Parameter`
schema). Kept deliberately light to import (only astropy), so depending on core
does not drag in the heavy per-process science modules.
"""
from .image_data import ImageData
from .metadata_policy import MetadataPolicy
from .parameters import BoolParam, ChoiceParam, FloatParam, IntParam, Parameter
from .process import Operator, Process, sequential
from .process_spec import ProcessSpec
from .registry import Algorithm, Subprocess

__all__ = [
    "ImageData",
    "MetadataPolicy",
    "Parameter",
    "FloatParam",
    "IntParam",
    "BoolParam",
    "ChoiceParam",
    "Operator",
    "Process",
    "sequential",
    "ProcessSpec",
    "Algorithm",
    "Subprocess",
]
