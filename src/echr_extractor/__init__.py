"""ECHR Extractor - Python library for extracting ECHR case data."""

import logging

from .echr import get_echr, get_echr_extra, get_nodes_edges

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
    "get_echr",
    "get_echr_extra",
    "get_nodes_edges",
]
