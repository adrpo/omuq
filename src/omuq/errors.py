"""Exception hierarchy for omuq-python."""

from __future__ import annotations


class OmuqError(Exception):
    """Base class for all omuq-python errors."""


class PackageError(OmuqError):
    """The SSP archive is missing, malformed, or violates SSP packaging rules."""


class ModelError(OmuqError):
    """The document content is invalid for the requested operation.

    Raised by the builders and accessors in :mod:`omuq.model` when a
    domain rule is broken, for example an unknown enumeration value or a
    boundary whose points disagree on dimension. A plain
    :class:`TypeError` is reserved for type misuse, such as an unexpected
    keyword or an object of the wrong class.
    """


class FittingError(OmuqError):
    """A domain boundary cannot be fitted to the given point cloud."""


class AnchorError(OmuqError):
    """An anchor does not resolve to a legal MetaData carrier in the package."""


class AmbiguousPathError(AnchorError):
    """A dotted element path matches more than one element (name punning).

    SSP allows dots inside element names, so ``a.b.c`` may mean the element
    ``c`` inside ``b`` inside ``a``, or the element literally named ``b.c``
    inside ``a``, and so on. When more than one interpretation matches,
    callers must disambiguate by passing the path as an explicit tuple.
    """

    def __init__(self, dotted: str, matches: list[tuple[str, ...]]):
        self.dotted = dotted
        self.matches = matches
        opts = ", ".join("/".join(m) for m in matches)
        super().__init__(
            f"element path {dotted!r} is ambiguous; candidates: {opts}. "
            "Pass the path as a tuple of names to disambiguate."
        )


class LinkError(OmuqError):
    """A MetaData link or an external source URI cannot be resolved."""


class DuplicateStudyError(OmuqError):
    """A study with the same name is already attached in this package."""


class SimulationError(OmuqError):
    """A simulation run cannot be configured or driven to completion."""


class DriverNotFoundError(SimulationError):
    """The requested simulator backend is not installed or not reachable."""
