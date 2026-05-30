"""Serves the pipeline pages (one per first-order process).

Each page is rendered from a template in ``pmo_stacklab/templates``. Routing is
data-driven so adding or reordering pages is a one-line change here, mirroring
the data-driven philosophy of the pipeline itself.
"""
from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)

# URL route -> template file
_PAGES = {
    "/": "home.html",
    "/upload": "upload.html",
    "/calibrate": "calibrate.html",
    "/reproject": "reproject.html",
    "/stack": "stack.html",
    "/postprocess": "postprocess.html",
}


def _make_view(template_name):
    def view():
        return render_template(template_name)

    return view


for _route, _template in _PAGES.items():
    pages_bp.add_url_rule(
        _route,
        endpoint=_template.removesuffix(".html"),
        view_func=_make_view(_template),
    )
