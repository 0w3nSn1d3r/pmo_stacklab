"""PMO StackLab - interactive, pedagogical astrophotography image stacking.

The package is intentionally light at import time: the Flask application is
built via :func:`pmo_stacklab.app.factory.build_app`, and the (heavy) science
modules under :mod:`pmo_stacklab.modules` are imported lazily by the pipeline
when a stacking job actually runs.
"""

__version__ = "0.1.0"
