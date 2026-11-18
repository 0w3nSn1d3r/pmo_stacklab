"""Core pipeline infrastructure.

Houses the building blocks shared across all processes: the generic
:class:`Process` class and its declarative :class:`ProcessSpec`, the
:class:`ImageData` container threaded through the pipeline, its
:class:`MetadataPolicy`, and the generalized algorithm builder
(:class:`Algorithm` / :class:`Subprocess` plus the typed :class:`Parameter`
schema). Kept deliberately light to import (only astropy), so depending on core
does not drag in the heavy per-process science modules.
"""
from .color import COLOR_COMBINE, LUMINANCE_APPLY, NORMALIZATION
from .color_combine import (
    Combiner,
    Normalizer,
    apply_gain,
    build_minmax_normalizer,
    build_percentile_normalizer,
    build_sky_normalizer,
    combine_image_data,
    mix_colors,
    normalize_plane,
    parse_color,
)
from .luminance import LuminanceOp
from .errors import PipelineError
from .image_data import ImageData
from .loader import DEFAULT_UNIT, load_frame, load_frames, load_image_data
from .metadata_policy import MetadataPolicy
from .metrics import frame_metrics
from .parameters import BoolParam, ChoiceParam, FloatParam, IntParam, Parameter
from .pipeline import Pipeline, PipelineSpec
from .preview import DEFAULT_MAX_SIDE, downsample, render_png
from .process import Operator, Process, sequential
from .process_spec import ProcessSpec
from .registry import Algorithm, Subprocess
from .rgb_image import CHANNELS, RGBImage

__all__ = [
    "ImageData",
    "RGBImage",
    "CHANNELS",
    "PipelineError",
    "MetadataPolicy",
    "DEFAULT_UNIT",
    "load_frame",
    "load_frames",
    "load_image_data",
    "DEFAULT_MAX_SIDE",
    "downsample",
    "render_png",
    "frame_metrics",
    "COLOR_COMBINE",
    "LUMINANCE_APPLY",
    "NORMALIZATION",
    "Combiner",
    "Normalizer",
    "apply_gain",
    "build_minmax_normalizer",
    "build_percentile_normalizer",
    "build_sky_normalizer",
    "LuminanceOp",
    "combine_image_data",
    "mix_colors",
    "normalize_plane",
    "parse_color",
    "Parameter",
    "FloatParam",
    "IntParam",
    "BoolParam",
    "ChoiceParam",
    "Operator",
    "Process",
    "sequential",
    "ProcessSpec",
    "Pipeline",
    "PipelineSpec",
    "Algorithm",
    "Subprocess",
]
