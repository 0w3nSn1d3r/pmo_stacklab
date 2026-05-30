"""The generic Process class -- one type for all five first-order processes.

A Process is a thin, uniform wrapper around the three things every first-order
process (Upload, Calibrate, Reproject, Stack, Post-Process) needs:

* a ``name`` -- used for routing, previews, and display;
* a tuple of ``operators`` -- the per-subprocess callables, already configured
  with the user's chosen algorithm and parameters; and
* a ``coordinator`` -- the function that runs those operators over the working
  :class:`~pmo_stacklab.modules.core.image_data.ImageData` to produce the
  process's output.

Because every process is just an *instance* of this one class, the generalized
endpoint can drive any of them through the identical :meth:`Process.run` call;
what differs between processes is only the operators they hold and the
coordinator that knows how to sequence them. Linear processes (Reproject,
Post-Process) use the :func:`sequential` coordinator; processes with richer
structure (Calibrate's master-frame construction, Stack's collapse) supply their
own coordinator.

The class is generic in the operator type ``Op`` because operators are not
uniform across processes: most are ``ImageData -> ImageData`` transforms (see
:data:`Operator`), but, for example, Stack's operators are frame-combining
functions consumed by :meth:`ImageData.collapse_lights`. Each process pins
``Op`` to its own operator shape and supplies a coordinator typed to match.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Sequence
from typing import Generic, TypeVar

from .image_data import ImageData

#: The operator type a Process holds. Left generic because it is
#: process-specific (see the module docstring).
Op = TypeVar("Op")

#: The common operator shape: a configured subprocess that transforms the
#: working data. Used by linear processes and by the :func:`sequential`
#: coordinator.
Operator = Callable[[ImageData], ImageData]


@dataclass(frozen=True)
class Process(Generic[Op]):
    """A single first-order process: a named, coordinated bundle of operators.

    Instances are immutable configuration objects, built per session from the
    user's submitted pipeline configuration and indexed in pipeline order by the
    generalized endpoint. Construct one instance per process -- do not subclass
    per process.

    :param name: human-facing process name (e.g. ``"Calibrate"``); also used to
        address the process in routing and previews.
    :param operators: the per-subprocess callables, in coordinator-defined order,
        each already configured with the user's chosen algorithm and parameters.
    :param coordinator: runs ``operators`` over an :class:`ImageData` to produce
        the process output. It receives the operators and the input data, so the
        same coordinator function can be reused across processes of the same
        shape (e.g. :func:`sequential`).
    """

    name: str
    operators: tuple[Op, ...]
    coordinator: Callable[[Sequence[Op], ImageData], ImageData]

    def run(self, data: ImageData) -> ImageData:
        """Execute the process by handing its operators and input to the coordinator.

        :param data: the working data from the previous pipeline step (or the
            uploaded frames, for the first step).
        :returns: this process's output, to be previewed and passed to the next
            process.
        """
        return self.coordinator(self.operators, data)


def sequential(operators: Sequence[Operator], data: ImageData) -> ImageData:
    """Coordinator that applies each operator in order, threading the data through.

    This is the default coordinator for *linear* processes -- those whose
    subprocesses are independent ``ImageData -> ImageData`` transforms applied
    one after another (e.g. Reproject's register -> align, or Post-Process's
    background -> colour -> stretch -> scale). It is a simple left fold: the
    output of each operator becomes the input of the next.

    :param operators: configured subprocess operators, in application order.
    :param data: the input working data.
    :returns: the data after every operator has been applied in sequence.
    """
    for operator in operators:
        data = operator(data)
    return data
