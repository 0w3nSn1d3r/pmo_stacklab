"""The generalized algorithm builder: a typed, name-addressed registry of algorithms.

This is the backend half of the project's central abstraction. Each *subprocess*
(a second-order step such as "outlier rejection" or "stretch") offers a set of
*algorithms*; the user picks one and supplies its parameters, and the endpoint
must turn that choice into a ready-to-call, parameter-configured callable -- for
ANY process -- through one uniform mechanism.

An :class:`Algorithm` couples three things: a name, a tuple of typed
:class:`~pmo_stacklab.modules.core.parameters.Parameter` descriptors (its schema),
and a *builder* that, given validated parameters, returns the configured callable.
A :class:`Subprocess` groups the algorithms available for one slot and can serve
its whole schema as JSON.

Deliberate generality (do not erode this): the builder's return value is typed as
``object`` and is NEVER inspected here. Different processes produce callables of
different shapes -- Stack's are cube reducers, Calibrate's are ImageData
transforms, and Reproject's / Post-Process's (not yet written) will differ again.
The registry's job ends at "validate the parameters, call the builder, hand back
whatever it returns"; only the owning process's coordinator knows how to use that
callable. Likewise, builders receive ONLY user parameters -- never image data or
side inputs, which the configured callable obtains at call time from the
:class:`~pmo_stacklab.modules.core.image_data.ImageData` container.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .parameters import Parameter


@dataclass(frozen=True)
class Algorithm:
    """One selectable algorithm: a name, a parameter schema, and a builder.

    :param name: identifier, unique within its subprocess (e.g. ``"sigma_clip"``).
    :param builder: called with the validated parameters as keyword arguments and
        returns the configured callable. Its return type is intentionally
        unconstrained -- see the module docstring.
    :param parameters: the algorithm's typed parameter schema (may be empty).
    :param label: optional human-facing display name (defaults to ``name``).
    :param description: optional explanation for the GUI / pedagogy.
    """

    name: str
    builder: Callable[..., object]
    parameters: tuple[Parameter, ...] = ()
    label: str = ""
    description: str = ""

    def build(self, raw_params: Mapping[str, object] | None = None) -> object:
        """Validate ``raw_params`` against the schema, then build the configured callable.

        Each declared parameter is validated against the submitted value; a
        parameter the user omits falls back to its default. Keys not in the schema
        are ignored, so incidental frontend fields do not break the build.

        :param raw_params: the user's submitted parameter values (name -> value).
        :returns: whatever the builder returns -- the parameter-configured callable.
        :raises ValueError: if any submitted value fails its parameter's validation.
        """
        raw = raw_params or {}
        kwargs = {
            param.name: (
                param.validate(raw[param.name])
                if param.name in raw
                else param.default
            )
            for param in self.parameters
        }
        return self.builder(**kwargs)

    def to_dict(self) -> dict[str, object]:
        """Serialize the algorithm and its parameter schema for the JSON contract."""
        return {
            "name": self.name,
            "label": self.label or self.name,
            "description": self.description,
            "parameters": [param.to_dict() for param in self.parameters],
        }


@dataclass(frozen=True)
class Subprocess:
    """One configurable subprocess slot: a name and the algorithms it offers.

    The frontend renders a :class:`Subprocess` as a choice of algorithm (a radio
    group) whose selection reveals that algorithm's parameter controls; the
    backend uses it to build the chosen, configured operator.

    :param name: the subprocess's identifier (e.g. ``"outlier_rejection"``).
    :param algorithms: the algorithms the user may choose between for this slot.
    :param label: optional human-facing display name (defaults to ``name``).
    :param description: optional explanation for the GUI / pedagogy.
    """

    name: str
    algorithms: tuple[Algorithm, ...]
    label: str = ""
    description: str = ""

    def algorithm(self, name: str) -> Algorithm:
        """Return the algorithm called ``name``; raise ``KeyError`` if absent."""
        for algorithm in self.algorithms:
            if algorithm.name == name:
                return algorithm
        raise KeyError(f"subprocess {self.name!r} has no algorithm {name!r}")

    def build(self, name: str, raw_params: Mapping[str, object] | None = None) -> object:
        """Build the configured callable for the chosen algorithm ``name``.

        :param name: the algorithm the user selected for this subprocess.
        :param raw_params: that algorithm's submitted parameter values.
        :returns: the parameter-configured callable produced by the algorithm.
        :raises KeyError: if ``name`` is not an algorithm of this subprocess.
        :raises ValueError: if a submitted parameter value is invalid.
        """
        return self.algorithm(name).build(raw_params)

    def to_dict(self) -> dict[str, object]:
        """Serialize this subprocess and all its algorithms' schemas as JSON."""
        return {
            "name": self.name,
            "label": self.label or self.name,
            "description": self.description,
            "algorithms": [algorithm.to_dict() for algorithm in self.algorithms],
        }
