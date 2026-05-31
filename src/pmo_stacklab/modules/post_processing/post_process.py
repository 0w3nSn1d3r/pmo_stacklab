"""The Post-Process process: finish the stacked image for display.

Post-Process is the final pipeline step: it takes the single integrated frame of
each filter and prepares it for viewing -- subtract the sky background, normalize
the intensity range, and apply a non-linear stretch so faint structure shows.

Unlike Stack and Reproject, Post-Process is a genuinely *linear* process: its
subprocesses are independent ``ImageData -> ImageData`` grayscale transforms
applied one after another, so it uses the shared :func:`sequential` coordinator
directly with no custom logic.

NOTE: colour mapping (combining per-filter frames into a single RGB image) is a
deliberate later unit -- it collapses the per-filter structure and needs its own
ImageData/RGB design -- so this process is per-filter grayscale for now.
"""
from __future__ import annotations

from ..core import Operator, Process, sequential


def build_post_process(*operators: Operator) -> Process[Operator]:
    """Build the Post-Process :class:`Process` from chosen operators.

    :param operators: the post-processing operators in application order,
        conventionally background -> intensity-scaling -> stretch. Omit any step
        you do not want applied.
    :returns: a Post-Process process ready to ``run`` on an :class:`ImageData`.
    """
    return Process(
        name="Post-Process",
        operators=tuple(operators),
        coordinator=sequential,
    )
