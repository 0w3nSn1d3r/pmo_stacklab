"""Entry point: ``python -m pmo_stacklab`` launches the development server."""
from .app.factory import build_app


def main():
    app = build_app()
    app.run(debug=True)


if __name__ == "__main__":
    main()
