"""Typed parameter descriptors -- the schema half of the generalized algorithm builder.

Every algorithm in the pipeline declares its parameters as a tuple of
:class:`Parameter` descriptors. A descriptor does exactly two jobs, so the schema
stays the single source of truth shared by backend and frontend:

* :meth:`Parameter.validate` -- coerce and bounds-check a user-submitted value on
  the backend; and
* :meth:`Parameter.to_dict` -- serialize the parameter (its type and constraints)
  so the frontend can render an appropriate control and the schema can be served
  as JSON.

The parameter *type* is kept deliberately general -- numeric, boolean, and
categorical are provided here, and new kinds (file references, composite ranges,
...) are added simply by subclassing :class:`Parameter`. Crucially, HOW a
parameter is rendered (slider, dropdown, checkbox, ...) is a frontend decision
driven by the serialized ``type``; the backend only validates. Nothing here
assumes a parameter is numeric or maps to a slider -- in particular
:class:`ChoiceParam` is a first-class non-ordinal category, never a position on a
scale.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Parameter(ABC):
    """Base class for a single algorithm parameter.

    :param name: the parameter's identifier; also the keyword the builder receives.
    :param default: the value used when the user supplies none.
    :param description: human-facing explanation (for GUI tooltips / pedagogy).
    """

    name: str
    default: object
    description: str = ""

    @abstractmethod
    def validate(self, value: object) -> object:
        """Coerce and bounds-check ``value``; raise ``ValueError`` if invalid."""

    @abstractmethod
    def to_dict(self) -> dict[str, object]:
        """Serialize this parameter (type + constraints) for the JSON schema."""


@dataclass(frozen=True, kw_only=True)
class FloatParam(Parameter):
    """A real-valued parameter, optionally bounded.

    :param default: value used when the user supplies none.
    :param minimum: inclusive lower bound, or ``None`` for unbounded.
    :param maximum: inclusive upper bound, or ``None`` for unbounded.
    :param step: suggested UI increment (advisory only; not enforced).
    """

    default: float
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None

    def validate(self, value: object) -> float:
        try:
            result = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(f"{self.name}: expected a number, got {value!r}")
        if self.minimum is not None and result < self.minimum:
            raise ValueError(f"{self.name}: {result} is below minimum {self.minimum}")
        if self.maximum is not None and result > self.maximum:
            raise ValueError(f"{self.name}: {result} is above maximum {self.maximum}")
        return result

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": "float",
            "default": self.default,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "description": self.description,
        }


@dataclass(frozen=True, kw_only=True)
class IntParam(Parameter):
    """An integer parameter, optionally bounded."""

    default: int
    minimum: int | None = None
    maximum: int | None = None
    step: int = 1

    def validate(self, value: object) -> int:
        try:
            # Reject non-integral floats (e.g. 2.5) rather than silently truncating.
            if isinstance(value, float) and not value.is_integer():
                raise ValueError
            result = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(f"{self.name}: expected an integer, got {value!r}")
        if self.minimum is not None and result < self.minimum:
            raise ValueError(f"{self.name}: {result} is below minimum {self.minimum}")
        if self.maximum is not None and result > self.maximum:
            raise ValueError(f"{self.name}: {result} is above maximum {self.maximum}")
        return result

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": "int",
            "default": self.default,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "description": self.description,
        }


@dataclass(frozen=True, kw_only=True)
class BoolParam(Parameter):
    """A boolean (on/off) parameter."""

    default: bool

    def validate(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ValueError(f"{self.name}: expected a boolean, got {value!r}")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": "bool",
            "default": self.default,
            "description": self.description,
        }


@dataclass(frozen=True, kw_only=True)
class ChoiceParam(Parameter):
    """A categorical parameter: one value from a fixed set of choices.

    This is the non-ordinal, non-numeric case the architecture insists on
    supporting first-class (e.g. a debayer pattern, an interpolation kind). The
    frontend may render it however it likes, but the backend treats it strictly as
    membership in a set -- never as a position on a numeric scale.

    :param choices: the allowed values, in display order.
    :param default: the initially-selected choice (must be one of ``choices``).
    """

    choices: tuple[str, ...]
    default: str

    def __post_init__(self) -> None:
        if self.default not in self.choices:
            raise ValueError(
                f"{self.name}: default {self.default!r} is not among choices {self.choices}"
            )

    def validate(self, value: object) -> str:
        if value not in self.choices:
            raise ValueError(f"{self.name}: {value!r} is not one of {self.choices}")
        return value  # type: ignore[return-value]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": "choice",
            "choices": list(self.choices),
            "default": self.default,
            "description": self.description,
        }
