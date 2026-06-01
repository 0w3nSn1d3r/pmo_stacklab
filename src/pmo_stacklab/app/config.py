"""Application configuration, including the user-configurable pipeline order."""
from __future__ import annotations

from datetime import timedelta

from ..modules.calibration import CALIBRATE
from ..modules.core import PipelineSpec
from ..modules.post_processing import POST_PROCESS
from ..modules.reprojection import REPROJECT
from ..modules.stacking import STACK

# Reserved for future session-store eviction (the in-memory store does not yet
# expire entries).
SESSION_TTL = timedelta(hours=2)

# The pipeline: an ordered tuple of ProcessSpecs. The generalized /api/run endpoint
# indexes this to resolve the requested process and locate its input (the previous
# process's output). Upload supplies the initial data ahead of the first entry.
ORDER = (CALIBRATE, REPROJECT, STACK, POST_PROCESS)

# The whole pipeline as one spec -- used by Quick Stack to build and run every
# process from a saved recipe in one shot.
PIPELINE = PipelineSpec(processes=ORDER)

# The factory-default Quick Stack recipe: effective, simple settings chosen to
# work across the widest range of stacks. Each calibration step no-ops if its
# frames are absent, so this recipe is safe even for lights-only uploads.
#   Calibrate  : bias + exposure-scaled dark + flat.
#   Reproject  : astroalign star-matching (needs no WCS) + bilinear resampling.
#   Stack      : kappa-sigma clipping (sigma=3) then mean -- the standard, robust
#                best-SNR default.
#   Post-Process: global-median background, percentile scaling, asinh stretch.
DEFAULT_QUICKSTACK_RECIPE: dict[str, dict[str, dict[str, object]]] = {
    "Calibrate": {
        "bias_subtraction": {"algorithm": "subtract", "params": {}},
        "dark_subtraction": {"algorithm": "subtract", "params": {"scale": True}},
        "flat_fielding": {"algorithm": "divide", "params": {}},
    },
    "Reproject": {
        "registration": {"algorithm": "astroalign", "params": {"detection_sigma": 5.0}},
        "alignment": {"algorithm": "bilinear", "params": {}},
    },
    "Stack": {
        "outlier_rejection": {"algorithm": "sigma_clip", "params": {"sigma": 3.0}},
        "coaddition": {"algorithm": "mean", "params": {}},
    },
    "Post-Process": {
        "background": {"algorithm": "global", "params": {}},
        "intensity_scaling": {"algorithm": "percentile", "params": {"percentile": 99.0}},
        "stretch": {"algorithm": "asinh", "params": {"a": 0.1}},
    },
}
