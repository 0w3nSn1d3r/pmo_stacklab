"""The generalized process API: one endpoint runs any process; one serves any schema.

Routes (mounted under ``/api``):

* ``POST /api/upload``            -- load uploaded FITS frames into the session's
                                     initial ImageData (the Upload process).
* ``GET  /api/schema``            -- the pipeline as an ordered list of process names.
* ``GET  /api/schema/<process>``  -- the full parameter schema for one process.
* ``POST /api/run``               -- run a named process on the session's data.
* ``GET  /api/preview/<step>``    -- the filters available to preview for a step.
* ``GET  /api/preview/<step>/<filter>.png`` -- a display-stretched preview image.

The run endpoint is generic because it acts only on the ProcessSpec abstraction:
it looks the requested process up in the configured pipeline (``config.ORDER``),
builds it from the submitted per-subprocess choices, runs it on the previous step's
output (fetched from the session store), persists its output for the next step, and
returns a small summary. Adding or reordering processes is a change to ``ORDER``
alone.
"""
from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify, request

from ..config import ORDER
from ..store import SessionStore
from ..utils import session_id
from ...modules.core import ImageData, ProcessSpec, load_image_data, render_png

process_bp = Blueprint("process", __name__)

#: Store key for the uploaded (initial) ImageData, before any process has run.
#: Populated by ``POST /api/upload`` and read as the input to the first process.
UPLOAD_KEY = "__upload__"

#: Multipart field names accepted by the upload endpoint, mapping each to its
#: role in :func:`load_image_data`.
FRAME_FIELDS = ("lights", "darks", "bias", "flats")


def _store() -> SessionStore:
    return current_app.extensions["pmo_store"]


def _find(process_name: str | None) -> tuple[int | None, ProcessSpec | None]:
    """Return ``(index, spec)`` for ``process_name`` in ORDER, or ``(None, None)``."""
    for index, spec in enumerate(ORDER):
        if spec.name == process_name:
            return index, spec
    return None, None


@process_bp.post("/upload")
def upload():
    """Load uploaded FITS frames into the session's initial ImageData.

    Accepts a multipart form whose file fields are named by frame role
    (``lights``, ``darks``, ``bias``, ``flats``); each field may carry multiple
    files. At least one light frame is required. The resulting ImageData is stored
    under :data:`UPLOAD_KEY` as the input to the first pipeline process.
    """
    streams = {
        field: [f.stream for f in request.files.getlist(field)]
        for field in FRAME_FIELDS
    }
    if not streams["lights"]:
        return jsonify({"error": "at least one light frame is required"}), 400

    try:
        data = load_image_data(
            lights=streams["lights"],
            darks=streams["darks"],
            bias=streams["bias"],
            flats=streams["flats"],
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    store = _store()
    store.put(session_id(), UPLOAD_KEY, data)

    # Confirm every uploaded set so the user can verify what was received.
    summary = _summarise("Upload", data)
    summary["calibration"] = {
        "darks": len(data.darks),
        "bias": len(data.bias),
        "flats": {filt: len(frames) for filt, frames in data.flats.items()},
    }
    return jsonify(summary)


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
    """A minimal JSON-safe summary of a process output."""
    return {
        "process": process_name,
        "stacked": data.is_stacked,
        "filters": {
            filt: {"frames": len(frames), "shape": list(frames[0].data.shape)}
            for filt, frames in data.lights.items()
        },
    }


# A "step" addressable for preview is any pipeline process plus the synthetic
# "Upload" step, whose data lives under UPLOAD_KEY rather than a process name.
UPLOAD_STEP = "Upload"


def _step_data(step: str) -> ImageData | None:
    """Return the stored ImageData for a preview ``step`` name, or ``None``.

    ``step`` is a process name from ORDER, or :data:`UPLOAD_STEP` for the uploaded
    frames. Unknown names yield ``None`` (so the caller can 404).
    """
    if step == UPLOAD_STEP:
        key: str | None = UPLOAD_KEY
    else:
        _, spec = _find(step)
        key = spec.name if spec is not None else None
    if key is None:
        return None
    return _store().get(session_id(), key)


@process_bp.get("/preview/<step>")
def preview_filters(step: str):
    """List the filters available to preview for a completed ``step``."""
    data = _step_data(step)
    if data is None:
        return jsonify({"error": f"no preview available for {step!r}"}), 404
    return jsonify({"step": step, "filters": list(data.filters)})


@process_bp.get("/preview/<step>/<filter_name>.png")
def preview_image(step: str, filter_name: str):
    """Render a display-stretched PNG preview of one filter's frame at ``step``.

    Query params (display-only; never touch the stored data):

    * ``stretch`` -- display stretch name (default ``asinh``). Post-Process output
      is already display-ready, so the frontend requests it with ``linear``.
    * ``intensity`` -- faint-boost knob in [0, 1] (default 0.5).

    If the step produced several frames for the filter (i.e. it has not been
    stacked yet), the first frame is previewed.
    """
    data = _step_data(step)
    if data is None or filter_name not in data.lights:
        return jsonify({"error": f"no preview for {step!r} / {filter_name!r}"}), 404

    stretch = request.args.get("stretch", "asinh")
    try:
        intensity = float(request.args.get("intensity", 0.5))
    except ValueError:
        return jsonify({"error": "intensity must be a number"}), 400

    frame = data.lights[filter_name][0]
    try:
        png = render_png(frame, stretch=stretch, intensity=intensity)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # no-store: previews are cheap to regenerate and vary with the display controls.
    return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})
