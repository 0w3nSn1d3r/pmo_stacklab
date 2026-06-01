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
    # the per-session working data. QUICKSTACK_CONFIG_PATH is where the persisted
    # Quick Stack recipe lives (the single-user app keeps one under the instance
    # folder); a multi-user build would key it per user.
    #
    # The upload limits guard against a single request exhausting the machine's RAM
    # (frames are held in memory): MAX_CONTENT_LENGTH caps the whole request body
    # (Werkzeug aborts oversize requests with 413), and MAX_FRAMES_PER_UPLOAD caps
    # the frame count per upload. Both are tunable per deployment.
    app.config.update(
        SECRET_KEY=os.environ.get("PMO_STACKLAB_SECRET", "dev-only-change-me"),
        QUICKSTACK_CONFIG_PATH=os.environ.get(
            "PMO_STACKLAB_QUICKSTACK",
            os.path.join(app.instance_path, "quickstack.json"),
        ),
        MAX_CONTENT_LENGTH=int(
            os.environ.get("PMO_STACKLAB_MAX_UPLOAD_BYTES", 2 * 1024 * 1024 * 1024)
        ),  # 2 GiB total request body
        MAX_FRAMES_PER_UPLOAD=int(
            os.environ.get("PMO_STACKLAB_MAX_FRAMES", 500)
        ),
    )
    if config:
        app.config.update(config)

    # Per-app session store holding each session's working ImageData between
    # pipeline steps. Idle sessions are evicted after SESSION_TTL so memory does
    # not grow without bound over a long observing session. Behind the
    # SessionStore interface so a disk-backed, multi-user store can replace it
    # without touching the endpoint.
    from .config import SESSION_TTL
    from .store import InMemoryStore

    app.extensions["pmo_store"] = InMemoryStore(ttl=SESSION_TTL)

    # Blueprints are imported here (not at module load) to avoid import cycles.
    from .blueprints.pages import pages_bp
    from .blueprints.process import process_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(process_bp, url_prefix="/api")

    return app
