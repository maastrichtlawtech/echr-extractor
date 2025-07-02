"""ECHR Extractor - Python library for extracting ECHR case data."""

import logging

from .echr import get_echr, get_echr_extra, get_nodes_edges

__version__ = "1.0.44"
__author__ = "LawTech Lab, Maastricht University"
__email__ = "lawtech@maastrichtuniversity.nl"

# Configure logging
logging.basicConfig(level=logging.INFO)

__all__ = [
    "get_echr",
    "get_echr_extra", 
    "get_nodes_edges",
]
