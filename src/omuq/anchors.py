"""Anchor types: where omuq data may attach inside an SSP package.

SSP 2.0 permits ``ssc:MetaData`` on exactly these carriers (verified against
the official XSDs):

* the ``SystemStructureDescription`` root of an SSD,
* every ``TElement`` (``System``, ``Component``, ``SignalDictionaryReference``),
* each ``ParameterBinding`` inside an SSD,
* the ``ParameterSet`` root of an SSV file
  (and the roots of SSM and SSB files, not exposed by this SDK yet).

omuq-python models the supported subset as four anchor classes. Element
paths are tuples of element names below the root ``System``; the empty
tuple addresses the root ``System`` element itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SsdRootAnchor:
    """The ``SystemStructureDescription`` document root of an SSD entry.

    Names inside the attached study resolve hierarchically from the root
    system (``plant.battery.R0``).
    """

    ssd_name: str = "SystemStructure.ssd"


@dataclass(frozen=True)
class ElementAnchor:
    """A ``System``/``Component``/``SignalDictionaryReference`` in an SSD.

    ``path`` is relative to the root ``System``; ``()`` is the root
    ``System`` itself. Names inside the attached study resolve relative to
    the anchored element (``R0``, not ``plant.battery.R0``).
    """

    path: tuple[str, ...] = field(default=())
    ssd_name: str = "SystemStructure.ssd"

    def __post_init__(self):  # tolerate lists
        object.__setattr__(self, "path", tuple(self.path))


@dataclass(frozen=True)
class ParameterBindingAnchor:
    """The ``index``-th ``ParameterBinding`` of the element at ``path``.

    Name scope is the same as for :class:`ElementAnchor` on the owning
    element.
    """

    path: tuple[str, ...]
    index: int = 0
    ssd_name: str = "SystemStructure.ssd"

    def __post_init__(self):
        object.__setattr__(self, "path", tuple(self.path))


@dataclass(frozen=True)
class SsvAnchor:
    """The ``ParameterSet`` root of an ``.ssv`` entry in the archive.

    Uncertain parameter names in the attached study are expected to match
    parameter names declared in the host SSV ("distribution overlay").
    """

    entry: str


Anchor = SsdRootAnchor | ElementAnchor | ParameterBindingAnchor | SsvAnchor
