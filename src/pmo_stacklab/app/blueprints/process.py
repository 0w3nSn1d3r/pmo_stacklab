"""The generalized process API: one endpoint runs any process; one serves any schema.

Routes (mounted under ``/api``):

* ``GET  /api/schema``            -- the pipeline as an ordered list of process names.
* ``GET  /api/schema/<process>``  -- the full parameter schema for one process.
* ``POST /api/run``               -- run a named process on the session's data.

The run endpoint is generic because it acts only on the ProcessSpec abstraction:
it looks the requested process up in the configured pipeline (``config.ORDER``),
builds it from the submitted per-subprocess choices, runs it on the previous step's
output (fetched from the session store), persists its output for the next step, and
returns a small summary. Adding or reordering processes is a change to ``ORDER``
alone.
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..config import ORDER
from ..store import SessionStore
from ..utils import session_id
from ...modules.core import ImageData, ProcessSpec

process_bp = Blueprint("process", __name__)

#: Store key for the uploaded (initial) ImageData, before any process has run. The
#: Upload process (a later unit) will populate it; until then it is seeded directly.
UPLOAD_KEY = "__upload__"


def _store() -> SessionStore:
    return current_app.extensions["pmo_store"]


def _find(process_name: str | None) -> tuple[int | None, ProcessSpec | None]:
    """Return ``(index, spec)`` for ``process_name`` in ORDER, or ``(None, None)``."""
    for index, spec in enumerate(ORDER):
        if spec.name == process_name:
            return index, spec
    return None, None


@process_bp.get("/schema")
def list_pipeline():
    """Return the configured pipeline as an ordered list of process names."""
    return jsonify({"order": [spec.name for spec in ORDER]})


@process_bp.get("/schema/<process_name>")
def process_schema(process_name: str):
    """Return one process's full parameter schema for the ConfigMenu to render."""
    _, spec = _find(process_name)
    if spec is None:
        return jsonify({"error": f"unknown process {process_name!r}"}), 404
    return jsonify(spec.to_dict())


@process_bp.post("/run")
def run():
    """Build the requested process from submitted choices, run it, and persist output."""
    payload = request.get_json(silent=True) or {}
    process_name = payload.get("process")
    configs = payload.get("configs") or {}

    index, spec = _find(process_name)
    if spec is None or index is None:
        return jsonify({"error": f"unknown process {process_name!r}"}), 404

    sid = session_id()
    store = _store()

    # The input is the previous step's output -- or, for the first process, the
    # uploaded data.
    input_key = ORDER[index - 1].name if index > 0 else UPLOAD_KEY
    input_data = store.get(sid, input_key)
    if input_data is None:
        hint = (
            "no uploaded data; upload frames first"
            if index == 0
            else f"no output from {input_key!r} yet; run it first"
        )
        return jsonify({"error": hint}), 409

    try:
        process = spec.build(configs)
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        output = process.run(input_data)
    except Exception as exc:  # surface pipeline failures as a clean 500
        return jsonify({"error": f"{spec.name} failed: {exc}"}), 500

    store.put(sid, spec.name, output)
    return jsonify(_summarise(spec.name, output))


def _summarise(process_name: str, data: ImageData) -> dict[str, object]:
    """A minimal JSON-safe summary of a process output (placeholder for the preview)."""
    return {
        "process": process_name,
        "stacked": data.is_stacked,
        "filters": {
            filt: {"frames": len(frames), "shape": list(frames[0].data.shape)}
            for filt, frames in data.lights.items()
        },
    }
