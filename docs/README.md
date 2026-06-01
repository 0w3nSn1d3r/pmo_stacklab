# PMO StackLab

Interactive, pedagogical astrophotography image-stacking software.

PMO StackLab exposes **every step and parameter** of the image-stacking pipeline
through a web GUI, so students can experiment with algorithm and parameter
choices, preview the results, read honest quality metrics, and learn how each
decision shapes the final image. It does not implement stacking algorithms
itself: it *coordinates* established libraries (Astropy, ccdproc, Astroalign,
scikit-image, SEP, NumPy/SciPy) and surfaces all their relevant controls.

---

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Running the app](#running-the-app)
- [Configuration](#configuration)
- [Using the app](#using-the-app)
- [The pipeline](#the-pipeline)
- [Quick Stack](#quick-stack)
- [Architecture](#architecture)
- [HTTP API reference](#http-api-reference)
- [Testing](#testing)
- [Deployment notes](#deployment-notes)

---

## Requirements

- **Python 3.11+**
- The scientific stack is installed automatically (see `pyproject.toml`):
  Flask, NumPy, Astropy, SciPy, scikit-image, ccdproc, Astroalign, Pillow.

## Installation

From the project root, in a virtual environment:

```bash
python -m venv .venv
# Windows:  .venv\Scripts\Activate.ps1
# Unix:     source .venv/bin/activate
pip install -e .
```

The editable install (`-e`) is recommended for development; a plain
`pip install .` works for a fixed deployment.

## Running the app

```bash
python -m pmo_stacklab
```

Open the printed URL (default **http://127.0.0.1:5000/**). To expose the app on
the local network (e.g. a server at the observatory), bind all interfaces:

```bash
python -c "from pmo_stacklab.app.lifecycle import run; run(host='0.0.0.0')"
```

> The built-in server is Flask's **development** server. For a real multi-user
> deployment, serve `pmo_stacklab.app.factory.build_app()` behind a production
> WSGI server (gunicorn/waitress) — see [Deployment notes](#deployment-notes).

## Configuration

Set via environment variables (read in `app/factory.py`):

| Variable | Default | Purpose |
|---|---|---|
| `PMO_STACKLAB_SECRET` | `dev-only-change-me` | Flask session secret. **Set this in any real deployment.** |
| `PMO_STACKLAB_QUICKSTACK` | `<instance>/quickstack.json` | Where the saved Quick Stack recipe is stored. |
| `PMO_STACKLAB_MAX_UPLOAD_BYTES` | `2147483648` (2 GiB) | Max total size of one upload request. |
| `PMO_STACKLAB_MAX_FRAMES` | `500` | Max number of frames per upload. |

The session's working data (every step's full-resolution image) is held in
memory and **evicted after 2 hours of inactivity** (`SESSION_TTL` in
`app/config.py`).

## Using the app

The navigation bar follows the pipeline left to right. A typical session:

1. **Upload** — choose your FITS frames by role (lights required; darks, bias,
   flats optional). Light and flat frames are grouped automatically by their
   `FILTER` header. Click **Upload Frames**.
2. **Calibrate → Reproject → Stack → Post-Process** — on each page, pick an
   algorithm per sub-step (each option has an **ⓘ** info tip explaining its role),
   adjust the parameter sliders, and click **Run**. After each run you get:
   - a **preview** (downsampled + display-stretched; the stretch controls affect
     only what you see, never the data);
   - a **metrics** table (computed on the full-resolution *linear* data, so the
     numbers are honest regardless of the display stretch);
   - a **before/after blink** toggle (same screen position, matched stretch) to
     see exactly what the step changed;
   - **click-to-zoom** into the full-resolution image;
   - a **Download** menu (full-resolution FITS or PNG).
3. **Color** — map your per-filter stacked frames onto the red/green/blue
   channels and combine them into one colour image (downloadable as PNG, or as a
   3-plane FITS cube).

## The pipeline

The five first-order processes, each a tunable step:

| Process | Sub-steps (algorithms) |
|---|---|
| **Upload** | Load FITS → the working data |
| **Calibrate** | Bias subtraction · dark subtraction (exposure-scaled) · flat fielding |
| **Reproject** | Registration (none / star-matching / phase-correlation / WCS) · alignment (nearest / bilinear / bicubic) |
| **Stack** | Outlier rejection (none / sigma-clip / winsorize / percentile-clip) · coaddition (median / mean / biweight / inverse-variance) |
| **Post-Process** | Background (none / global / 2-D) · intensity scaling (percentile / zscale / min-max) · stretch (asinh / log / sqrt / linear) |

Each process consumes the previous one's output. The pipeline order is defined in
`app/config.py` (`ORDER`).

## Quick Stack

On the Upload page, **Quick Stack** runs the whole saved recipe on the uploaded
frames in one click, then previews the final image (each step is still saved, so
the per-step preview/metrics/blink/download work afterward).

The gear menu beside it:
- **Configure** — walks you through each process page in config mode (the title
  reads e.g. *"Calibrate (Quick Stack Config)"* and the button becomes *Save &
  Continue*); your choices are saved into the recipe, running no frames.
- **Reset to Default** — restores the curated default recipe (bias + scaled dark
  + flat; star-matching + bilinear reprojection; sigma-clipped mean; global
  background + percentile scaling + asinh stretch) — chosen to work across the
  widest range of stacks.

The recipe persists on disk across restarts.

## Architecture

A three-tier, data-driven design (see `src/pmo_stacklab/modules/core/`):

- **`Process`** — one first-order process: a name, a tuple of configured
  sub-step *operators*, and a *coordinator* that runs them over the working data.
  Built declaratively from a **`ProcessSpec`** (the ordered subprocesses +
  coordinator).
- **`Subprocess` / `Algorithm`** — the registry: each sub-step offers selectable
  algorithms, each declaring a typed **`Parameter`** schema (float/int/bool/
  choice). The schema is the *single source of truth*: the backend validates
  against it and the frontend renders the GUI from it (`GET /api/schema/...`).
- **`ImageData`** — the immutable container threaded through every step: typed
  frame sets (light/dark/bias/flat) grouped by filter, each frame keeping its own
  WCS/header until the N→1 collapse at Stack.
- **`Pipeline` / `PipelineSpec`** — `Process` one level up: runs all processes in
  sequence (powers Quick Stack).
- **`RGBImage`** — the terminal colour result (kept separate so `ImageData`'s
  per-filter-grayscale invariant stays intact).

A single generalized endpoint (`POST /api/run`) drives *any* process by acting
only on the `ProcessSpec` abstraction, so adding or reordering a process is a
change to `ORDER` alone. To **add an algorithm**: write its builder + register it
as an `Algorithm` in that process's `algorithms.py`; it then appears in the GUI
automatically.

## HTTP API reference

All endpoints are under `/api` and return JSON (except image/file routes).
Errors are always `{"error": "..."}`; user-input faults give an actionable 4xx.

| Method & path | Purpose |
|---|---|
| `POST /upload` | Load uploaded FITS frames (multipart: `lights`/`darks`/`bias`/`flats`). |
| `GET /schema` | The pipeline as an ordered list of process names. |
| `GET /schema/<process>` | One process's full parameter schema. |
| `POST /run` | Run a process: body `{process, configs}`; persists + summarizes output. |
| `GET /preview/<step>` | Filters available to preview for a step. |
| `GET /preview/<step>/<filter>.png` | Display-stretched preview (`stretch`, `intensity`, `cx`/`cy` zoom). |
| `GET /metrics/<step>` | Per-filter quality metrics (full-res linear data). |
| `GET /download/<step>/<filter>.<fmt>` | Full-resolution download (`fits` or `png`). |
| `GET /quickstack` | Saved recipe + whole-pipeline schema. |
| `PUT /quickstack` | Validate and save a recipe. |
| `POST /quickstack/reset` | Reset the recipe to default. |
| `POST /quickstack/run` | Run the whole saved pipeline on the uploaded frames. |
| `GET /color` | Colour-combine schema + filters + default channel mapping. |
| `POST /color` | Combine mapped filters into an RGB image: body `{algorithm, params, mapping}`. |
| `GET /color.png` | The combined image (preview source). |
| `GET /color/download.<fmt>` | Download the combined image (`png` or 3-plane `fits`). |

## Testing

```bash
python -m unittest discover -s test -p "test_*.py"
```

Tests are standard-library `unittest` (no extra dependency) and cover the core
data model, every process and algorithm, the endpoints, error handling, and
frontend wiring. Frame fixtures are generated in memory — no fixture files on
disk.

## Deployment notes

The app is built **single-user, installed per machine**, with hygiene that makes
a future multi-user migration additive rather than a rewrite:

- Per-session state lives behind the `SessionStore` interface (`app/store.py`);
  the in-memory implementation can be swapped for a disk-backed/multi-tenant one
  without touching the endpoints.
- The Quick Stack config path is configurable per deployment.

A multi-user deployment would add: a production WSGI server, authentication
(e.g. university SSO), a background job queue for the heavy stacking work, and a
disk-backed session store with per-user quotas. None of these are required for
the single-user use at the observatory.
