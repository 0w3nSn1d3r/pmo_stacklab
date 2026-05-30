"""Application launch and teardown for PMO StackLab.

This module owns *running* the application, as opposed to *building* it (which
is the job of :func:`pmo_stacklab.app.factory.build_app`). Keeping the two
concerns separate means the factory stays a pure, side-effect-free constructor
that is trivial to import in tests, while all process-level behaviour -- binding
a port, starting the dev server, and (later) tearing things down -- lives here.

Right now "launch" means starting Flask's development server. When the
disk-backed, session-keyed store lands (see the deployment model), its
initialisation and graceful teardown -- e.g. flushing caches or evicting expired
sessions on shutdown -- will also be wired up in this module.
"""
from .factory import build_app


def run(host="127.0.0.1", port=5000, debug=True, config=None):
    """Build the application and start the development server.

    This is the entry point used by ``python -m pmo_stacklab`` (see
    :mod:`pmo_stacklab.__main__`).

    :param host: network interface to bind. Defaults to ``127.0.0.1``
        (localhost only), matching the current single-user deployment model;
        pass ``"0.0.0.0"`` to expose the server on the local network.
    :param port: TCP port to serve on.
    :param debug: enable Flask's interactive debugger and auto-reloader. Useful
        in development; must be ``False`` in any real deployment.
    :param config: optional mapping of config overrides forwarded to
        :func:`build_app`.

    NOTE: ``app.run()`` starts Werkzeug's development server, which is not
    suitable for production. A production deployment would instead serve the
    object returned by :func:`build_app` through a WSGI server.
    """
    app = build_app(config)
    app.run(host=host, port=port, debug=debug)
