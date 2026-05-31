"""Application factory for PMO StackLab."""
import os

from flask import Flask


def build_app(config=None):
    """Build and configure the Flask application.

    :param config: optional mapping of config overrides, applied last.
    :return: a configured :class:`flask.Flask` instance.
    """
    # Templates and static assets live at the package root
    # (pmo_stacklab/templates, pmo_stacklab/static), one level up from app/.
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(
        __name__,
        template_folder=os.path.join(pkg_root, "templates"),
        static_folder=os.path.join(pkg_root, "static"),
    )

    # Default configuration. SECRET_KEY is required for Flask sessions, which key
    # the per-session working data.
    app.config.update(
        SECRET_KEY=os.environ.get("PMO_STACKLAB_SECRET", "dev-only-change-me"),
    )
    if config:
        app.config.update(config)

    # Per-app session store holding each session's working ImageData between
    # pipeline steps. Behind the SessionStore interface so a disk-backed,
    # multi-user store can replace it without touching the endpoint.
    from .store import InMemoryStore

    app.extensions["pmo_store"] = InMemoryStore()

    # Blueprints are imported here (not at module load) to avoid import cycles.
    from .blueprints.pages import pages_bp
    from .blueprints.process import process_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(process_bp, url_prefix="/api")

    return app
