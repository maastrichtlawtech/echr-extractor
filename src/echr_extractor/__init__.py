"""ECHR Extractor - Python library for extracting ECHR case data."""

import logging

from .echr import (
    get_document_citations,
    get_echr,
    get_echr_extra,
    get_echr_segments,
    get_nodes_edges,
)
from .ECHR_reference_resolver import (
    parse_scl_references,
    resolve_references,
)
from .segmentation import (
    prepare_segmentation_corpus,
    segment_document,
    segment_documents,
)

try:
    from ._version import version as __version__
except ImportError:
    # Fallback for development without tags
    __version__ = "0.0.0.dev0"

__author__ = "LawTech Lab, Maastricht University"
__email__ = "lawtech@maastrichtuniversity.nl"

# Configure logging
logging.basicConfig(level=logging.INFO)

__all__ = [
    "get_document_citations",
    "get_echr",
    "get_echr_extra",
    "get_echr_segments",
    "get_nodes_edges",
    "parse_scl_references",
    "prepare_segmentation_corpus",
    "resolve_references",
    "segment_document",
    "segment_documents",
]
