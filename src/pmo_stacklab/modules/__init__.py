"""Backend science modules for the stacking pipeline.

Submodules (``calibration``, ``reprojection``, ``stacking``, ``post_processing``,
``core``) are imported explicitly where needed rather than eagerly here, so that
importing :mod:`pmo_stacklab` does not pull in the heavy scientific stack.
"""
