"""Pipeline -- run the whole sequence of processes in one shot.

A Pipeline is to the list of processes what a :class:`Process` is to its
subprocesses: the same idea one level up. Where a Process holds configured
subprocess *operators* and a coordinator that threads :class:`ImageData` through
them, a Pipeline holds configured *processes* as its operators and threads the
ImageData through each in turn. Because the pipeline is inherently sequential
(each process consumes the previous one's output), the coordinator is simply the
:func:`sequential` fold -- each :class:`Process` is already an
``ImageData -> ImageData`` callable via :meth:`Process.run`.

This is what powers "Quick Stack": rather than the user advancing through every
process by hand, a Pipeline built from their saved recipe applies them all to the
uploaded frames at once.

:class:`PipelineSpec` is the declarative counterpart (mirroring
:class:`~pmo_stacklab.modules.core.process_spec.ProcessSpec`): it holds the ordered
:class:`ProcessSpec`\\s and builds a runnable Pipeline from a full recipe -- a
mapping of process name -> that process's per-subprocess choices.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .image_data import ImageData
from .process import Process
from .process_spec import ProcessSpec

# A full pipeline recipe: process name -> that process's configs (the same
# per-subprocess {algorithm, params} mapping ProcessSpec.build accepts).
Recipe = Mapping[str, Mapping[str, Mapping[str, object]]]


@dataclass(frozen=True)
class Pipeline:
    """A runnable sequence of configured processes.

    :param processes: the configured :class:`Process` instances, in pipeline order.
    """

    processes: tuple[Process, ...]

    def run(self, data: ImageData) -> ImageData:
        """Apply every process in order, threading the data through each.

        Mirrors :func:`~pmo_stacklab.modules.core.process.sequential` at the
        pipeline level: the output of each process is the input to the next.

        :param data: the uploaded/initial working data.
        :returns: the data after the whole pipeline has run.
        """
        for process in self.processes:
            data = process.run(data)
        return data


@dataclass(frozen=True)
class PipelineSpec:
    """The declarative definition of the whole pipeline.

    :param processes: the ordered :class:`ProcessSpec`\\s (typically the configured
        pipeline ``ORDER``).
    """

    processes: tuple[ProcessSpec, ...]

    def build(self, recipe: Recipe | None = None) -> Pipeline:
        """Build a runnable :class:`Pipeline` from a full recipe.

        :param recipe: a mapping of process name -> that process's per-subprocess
            ``{algorithm, params}`` choices. A process absent from the recipe is
            built from its defaults (each :class:`ProcessSpec` falls back to its
            first algorithm per subprocess), so a partial or empty recipe still
            yields a runnable pipeline.
        :returns: a :class:`Pipeline` of configured processes, in pipeline order.
        :raises KeyError: if a recipe names an algorithm a subprocess does not
            offer.
        :raises ValueError: if a submitted parameter value is invalid, or the
            recipe is not a JSON object.
        """
        if recipe is not None and not isinstance(recipe, Mapping):
            raise ValueError(
                f"the recipe must be a JSON object, got {type(recipe).__name__}."
            )
        chosen = recipe or {}
        processes = tuple(
            spec.build(chosen.get(spec.name)) for spec in self.processes
        )
        return Pipeline(processes=processes)

    def default_recipe(self) -> dict[str, dict[str, dict[str, object]]]:
        """Return the recipe of every process's defaults (first algorithm, default params).

        This is the schema-derived baseline -- every subprocess's first algorithm
        with its default parameter values -- which the Quick Stack config layer can
        start from or override.
        """
        recipe: dict[str, dict[str, dict[str, object]]] = {}
        for spec in self.processes:
            process_recipe: dict[str, dict[str, object]] = {}
            for subprocess in spec.subprocesses:
                algorithm = subprocess.algorithms[0]
                process_recipe[subprocess.name] = {
                    "algorithm": algorithm.name,
                    "params": {
                        param.name: param.default for param in algorithm.parameters
                    },
                }
            recipe[spec.name] = process_recipe
        return recipe

    def to_dict(self) -> dict[str, object]:
        """Serialize every process's schema, in order (the whole-pipeline schema)."""
        return {"processes": [spec.to_dict() for spec in self.processes]}
