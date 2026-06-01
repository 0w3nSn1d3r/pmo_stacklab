"""Persisted Quick Stack configuration -- the user's saved one-click recipe.

Quick Stack applies a preconfigured pipeline recipe to the uploaded frames in one
shot. That recipe is a saved *preference*, so it persists on disk across restarts
(unlike the per-session working data). This module is the small store for it: load
the saved recipe, save a new one, or reset to the curated factory default.

The recipe is the same JSON shape the pipeline consumes -- process name -> that
process's per-subprocess ``{algorithm, params}`` choices -- so saving is just
validating and writing it, and running is handing it to ``PipelineSpec.build``.

In the single-user build there is one recipe file. The path is taken from app
config (``QUICKSTACK_CONFIG_PATH``), which is the seam a multi-user build would
use to key the recipe per user.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy

from .config import DEFAULT_QUICKSTACK_RECIPE

Recipe = dict[str, dict[str, dict[str, object]]]


def default_recipe() -> Recipe:
    """Return a deep copy of the factory-default Quick Stack recipe."""
    return deepcopy(DEFAULT_QUICKSTACK_RECIPE)


def load_recipe(path: str) -> Recipe:
    """Load the saved recipe from ``path``, or the factory default if none/invalid.

    A missing or unreadable file falls back to the default rather than erroring, so
    Quick Stack always has a usable recipe (the default is also what a fresh
    install starts from).
    """
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default_recipe()
    if not isinstance(data, dict):
        return default_recipe()
    return data


def save_recipe(path: str, recipe: Recipe) -> None:
    """Persist ``recipe`` to ``path`` as JSON, creating the directory if needed."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(recipe, handle, indent=2)


def reset_recipe(path: str) -> Recipe:
    """Reset the saved recipe to the factory default and persist it; return it."""
    recipe = default_recipe()
    save_recipe(path, recipe)
    return recipe
