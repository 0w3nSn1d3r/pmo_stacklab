"""ProcessSpec -- the declarative definition of a first-order process.

Where :class:`~pmo_stacklab.modules.core.process.Process` is the *runtime* object
(configured operators + coordinator, ready to run), a ProcessSpec is its
*declaration*: a process's name, its ordered subprocesses (each offering a choice
of algorithms), and the coordinator that will sequence the chosen operators. It is
the bridge from the algorithm registry to the runtime Process.

The generalized endpoint holds one ProcessSpec per pipeline step. Given the user's
submitted choices it calls :meth:`ProcessSpec.build` to produce a runnable
:class:`Process`; for the frontend it calls :meth:`ProcessSpec.to_dict` to serve
the whole process's schema.

A ProcessSpec is generic in its operator type ``Op`` so it can be paired with a
matching coordinator. The subprocesses' builders return ``object`` (the registry
is deliberately type-agnostic), so :meth:`build` re-asserts ``Op`` at that
boundary -- a guarantee the process author makes by pairing subprocesses whose
algorithms produce ``Op`` with a coordinator that consumes ``Op``.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from .image_data import ImageData
from .process import Process
from .registry import Subprocess

Op = TypeVar("Op")


@dataclass(frozen=True)
class ProcessSpec(Generic[Op]):
    """The declarative definition of one first-order process.

    :param name: the process's name (carried onto the runtime :class:`Process`).
    :param subprocesses: the process's subprocesses, in the order the coordinator
        expects the resulting operators (operator *i* is built from subprocess
        *i*).
    :param coordinator: the coordinator that runs the built operators over an
        :class:`ImageData` (e.g. ``sequential`` or a process-specific one).
    """

    name: str
    subprocesses: tuple[Subprocess, ...]
    coordinator: Callable[[Sequence[Op], ImageData], ImageData]

    def build(
        self, configs: Mapping[str, Mapping[str, object]] | None = None
    ) -> Process[Op]:
        """Build a runnable :class:`Process` from the user's submitted choices.

        :param configs: a mapping of subprocess name -> ``{"algorithm": <name>,
            "params": {<param>: <value>}}``. A subprocess omitted from ``configs``
            (or given no algorithm) falls back to its first algorithm with default
            parameters, so a partial submission still yields a runnable process.
        :returns: a :class:`Process` whose operators are built, in subprocess
            order, from the chosen algorithms and wired to this spec's coordinator.
        :raises KeyError: if a submitted algorithm name is not offered by its
            subprocess.
        :raises ValueError: if a submitted parameter value is invalid.
        """
        if configs is not None and not isinstance(configs, Mapping):
            raise ValueError(
                f"{self.name}: configuration must be a JSON object, got "
                f"{type(configs).__name__}."
            )
        chosen = configs or {}
        operators: list[Op] = []
        for subprocess in self.subprocesses:
            choice = chosen.get(subprocess.name) or {}
            if not isinstance(choice, Mapping):
                raise ValueError(
                    f"{self.name}: the {subprocess.name!r} setting must be a JSON "
                    f"object with an 'algorithm' (and optional 'params'), got "
                    f"{type(choice).__name__}."
                )
            algorithm = choice.get("algorithm") or subprocess.algorithms[0].name
            params = choice.get("params")
            # The registry erases the operator type to `object`; the spec
            # re-asserts Op, which its subprocess/coordinator pairing guarantees.
            operators.append(cast(Op, subprocess.build(algorithm, params)))  # type: ignore[arg-type]
        return Process(
            name=self.name, operators=tuple(operators), coordinator=self.coordinator
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the whole process schema (name + every subprocess) as JSON."""
        return {
            "name": self.name,
            "subprocesses": [subprocess.to_dict() for subprocess in self.subprocesses],
        }
