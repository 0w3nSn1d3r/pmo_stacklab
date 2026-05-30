"""Entry point: ``python -m pmo_stacklab`` launches the development server.

This stays deliberately thin -- it simply delegates to
:func:`pmo_stacklab.app.lifecycle.run`, which owns how the app is launched (and,
in future, torn down). Building the app itself lives in
:func:`pmo_stacklab.app.factory.build_app`.
"""
from .app.lifecycle import run


def main():
    run()


if __name__ == "__main__":
    main()
