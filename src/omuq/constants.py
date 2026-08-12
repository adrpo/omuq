"""Namespace URIs, MIME types, and packaging conventions used across omuq-python.

These constants implement the conventions fixed in the OMUQ-on-SSP
implementation guideline (see docs/IMPLEMENTATION_GUIDELINE.md):

* omuq data is linked from SSP host documents through SSP 2.0
  ``ssc:MetaData`` elements with ``kind="quality"``;
* omuq instance documents are stored as separate files under
  ``resources/uq/`` inside the SSP package;
* the primary MIME type is ``application/x-omuq``; the longer
  ``application/x-openscaling-uq`` is accepted as a read-side alias.
"""

from __future__ import annotations

# --- XML namespaces -------------------------------------------------------

NS_UQ = "http://openscaling.org/UQ1/UncertaintyQuantification"
NS_SSC = "http://ssp-standard.org/SSP1/SystemStructureCommon"
NS_SSD = "http://ssp-standard.org/SSP1/SystemStructureDescription"
NS_SSV = "http://ssp-standard.org/SSP1/SystemStructureParameterValues"
NS_STC = "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon"

#: Preferred prefixes when serializing omuq documents.
NSMAP = {"uq": NS_UQ, "ssc": NS_SSC, "ssv": NS_SSV, "stc": NS_STC}

# --- MIME types -----------------------------------------------------------

#: Primary MIME type written into ``ssc:MetaData/@type``.
MIME_OMUQ = "application/x-omuq"

#: All MIME types recognized as omuq content when reading.
MIME_ALIASES = frozenset({MIME_OMUQ, "application/x-openscaling-uq"})

# --- SSP MetaData conventions --------------------------------------------

#: ``ssc:MetaData/@kind`` used for omuq links. UQ and credibility data is
#: quality-related metadata in the sense of SSP 2.0 section 4.5.4.1.
DEFAULT_KIND = "quality"

#: Directory prefix inside the SSP archive where omuq documents live.
UQ_RESOURCE_DIR = "resources/uq"

#: Recommended file suffix for omuq instance documents.
UQ_SUFFIX = ".uq.xml"

#: SSP version stamped onto host documents that receive a MetaData node.
SSP_VERSION = "2.0"

# --- Tool identity --------------------------------------------------------

TOOL_NAME = "omuq-python"
TOOL_VERSION = "0.1.0"
GENERATION_TOOL = f"{TOOL_NAME} {TOOL_VERSION}"
