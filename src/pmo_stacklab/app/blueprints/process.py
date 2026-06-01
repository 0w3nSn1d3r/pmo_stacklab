"""The generalized process API: one endpoint runs any process; one serves any schema.

Routes (mounted under ``/api``):

* ``POST /api/upload``            -- load uploaded FITS frames into the session's
                                     initial ImageData (the Upload process).
* ``GET  /api/schema``            -- the pipeline as an ordered list of process names.
* ``GET  /api/schema/<process>``  -- the full parameter schema for one process.
* ``POST /api/run``               -- run a named process on the session's data.
* ``GET  /api/preview/<step>``    -- the filters available to preview for a step.
* ``GET  /api/preview/<step>/<filter>.png`` -- a display-stretched preview image.
* ``GET  /api/metrics/<step>``    -- per-filter quality metrics for a step.

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
from ...modules.core import (
    CHANNELS,
    COLOR_COMBINE,
    ImageData,
    ProcessSpec,
    RGBImage,
    combine_image_data,
    frame_metrics,
    load_image_data,
    render_png,
)
from PIL import Image
import io

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
    * ``cx``, ``cy`` -- optional fractional click centre in [0, 1] to zoom into. A
      fixed tile (a quarter of each dimension) centred there is rendered from the
      full-resolution frame, sharing the full-frame brightness mapping.

    If the step produced several frames for the filter (i.e. it has not been
    stacked yet), the first frame is previewed.
    """
    data = _step_data(step)
    if data is None or filter_name not in data.lights:
        return jsonify({"error": f"no preview for {step!r} / {filter_name!r}"}), 404

    stretch = request.args.get("stretch", "asinh")
    try:
        intensity = float(request.args.get("intensity", 0.5))
        region = _zoom_region(request.args.get("cx"), request.args.get("cy"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    frame = data.lights[filter_name][0]
    try:
        png = render_png(frame, stretch=stretch, intensity=intensity, region=region)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # no-store: previews are cheap to regenerate and vary with the display controls.
    return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})


#: Zoom tile size as a fraction of each dimension (a quarter-by-quarter region).
_ZOOM_FRACTION = 0.25


def _zoom_region(
    cx: str | None, cy: str | None
) -> tuple[float, float, float, float] | None:
    """Turn an optional fractional click centre into a fixed zoom region.

    :param cx, cy: the click centre as fractions in [0, 1], or ``None`` for no zoom.
    :returns: a fractional ``(x0, y0, x1, y1)`` region, or ``None`` when no centre
        is given. The tile is :data:`_ZOOM_FRACTION` of each dimension, centred on
        the click and shifted to stay within the image.
    :raises ValueError: if only one of ``cx``/``cy`` is given, or they are not
        numbers in [0, 1].
    """
    if cx is None and cy is None:
        return None
    if cx is None or cy is None:
        raise ValueError("both cx and cy are required to zoom")
    fx, fy = float(cx), float(cy)
    if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
        raise ValueError("cx and cy must be in [0, 1]")

    half = _ZOOM_FRACTION / 2.0
    # Centre the tile on the click, then clamp so it stays fully inside [0, 1].
    x0 = min(max(fx - half, 0.0), 1.0 - _ZOOM_FRACTION)
    y0 = min(max(fy - half, 0.0), 1.0 - _ZOOM_FRACTION)
    return (x0, y0, x0 + _ZOOM_FRACTION, y0 + _ZOOM_FRACTION)


@process_bp.get("/metrics/<step>")
def metrics(step: str):
    """Return per-filter quality metrics for a completed ``step``.

    Metrics are computed on the stored full-resolution, linear frame data (the
    first frame per filter), never on the display preview -- so the numbers
    describe the image, not the display stretch.
    """
    data = _step_data(step)
    if data is None:
        return jsonify({"error": f"no metrics available for {step!r}"}), 404
    return jsonify(
        {
            "step": step,
            "filters": {
                filt: frame_metrics(frames[0])
                for filt, frames in data.lights.items()
            },
        }
    )


# -- colour combination (a terminal step, parallel to the pipeline) -----------

#: Store key for the combined RGB image.
COLOR_KEY = "__color__"

#: Default filter-name -> channel guesses, so common setups pre-fill the mapping.
_CHANNEL_GUESS = {
    "red": ("R", "RED", "HA", "HALPHA", "SII", "S2"),
    "green": ("G", "GREEN", "V", "OIII", "O3"),
    "blue": ("B", "BLUE", "OIII", "O3", "HB"),
}


def _latest_stacked() -> tuple[str | None, ImageData | None]:
    """Find the most-processed stored step whose data is stacked (one frame/filter).

    Colour combination needs single, stacked frames; the natural source is the
    furthest-along step the session has produced. Walk the pipeline backward, then
    fall back to the uploaded data.
    """
    sid = session_id()
    store = _store()
    for spec in reversed(ORDER):
        candidate = store.get(sid, spec.name)
        if isinstance(candidate, ImageData) and candidate.is_stacked:
            return spec.name, candidate
    uploaded = store.get(sid, UPLOAD_KEY)
    if isinstance(uploaded, ImageData) and uploaded.is_stacked:
        return UPLOAD_STEP, uploaded
    return None, None


def _default_mapping(filters: list[str]) -> dict[str, str | None]:
    """Guess a channel->filter mapping from filter names; unguessed channels None."""
    upper = {f.upper(): f for f in filters}
    mapping: dict[str, str | None] = {}
    for channel in CHANNELS:
        mapping[channel] = next(
            (upper[name] for name in _CHANNEL_GUESS[channel] if name in upper), None
        )
    return mapping


@process_bp.get("/color")
def color_schema():
    """Return the combine-algorithm schema plus the source step's available filters.

    The frontend uses this to render the algorithm choice, the channel->filter
    dropdowns, and a sensible default mapping. 409 if nothing stacked exists yet.
    """
    step, data = _latest_stacked()
    if data is None:
        return jsonify({"error": "no stacked image to colour-combine yet"}), 409
    filters = list(data.filters)
    return jsonify(
        {
            "source": step,
            "filters": filters,
            "channels": list(CHANNELS),
            "default_mapping": _default_mapping(filters),
            "combine": COLOR_COMBINE.to_dict(),
        }
    )


@process_bp.post("/color")
def color_combine():
    """Combine the mapped per-filter frames into an RGB image and store it.

    JSON body: ``{"algorithm": <name>, "params": {...}, "mapping": {channel:
    filter}}``. Renders from the latest stacked step.
    """
    payload = request.get_json(silent=True) or {}
    mapping = payload.get("mapping") or {}
    algorithm = payload.get("algorithm")
    params = payload.get("params")

    _, data = _latest_stacked()
    if data is None:
        return jsonify({"error": "no stacked image to colour-combine yet"}), 409

    try:
        combiner = COLOR_COMBINE.build(algorithm or COLOR_COMBINE.algorithms[0].name, params)
        rgb = combine_image_data(data, mapping, combiner)
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    _store().put(session_id(), COLOR_KEY, rgb)
    return jsonify({"shape": list(rgb.shape), "mapping": rgb.mapping})


@process_bp.get("/color.png")
def color_image():
    """Serve the most recently combined RGB image as a PNG."""
    rgb = _store().get(session_id(), COLOR_KEY)
    if not isinstance(rgb, RGBImage):
        return jsonify({"error": "no colour image; combine first"}), 404
    buffer = io.BytesIO()
    Image.fromarray(rgb.data, mode="RGB").save(buffer, format="PNG")
    return Response(
        buffer.getvalue(), mimetype="image/png", headers={"Cache-Control": "no-store"}
    )
