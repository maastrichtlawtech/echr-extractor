"""ECHR full-text segmentation into structured legal sections.

Segments ECHR case texts into standard legal sections: procedure, facts,
complaints, law, operative, subject_matter, court_assessment,
separate_opinion, and appendix.

Uses a 3-stage pipeline:
  1. Route — choose parser mode from metadata/content
  2. Find boundaries — regex matching with validation
  3. Extract text — slice text between boundaries
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section names (output columns)
# ---------------------------------------------------------------------------
SECTION_NAMES = [
    "procedure",
    "facts",
    "complaints",
    "law",
    "operative",
    "subject_matter",
    "court_assessment",
    "separate_opinion",
    "appendix",
]

# ---------------------------------------------------------------------------
# Parser mode routing sets (metadata-based)
# ---------------------------------------------------------------------------
INFO_NOTE_DOCTYPES = {"CLIN", "CLINF"}
PRESS_RELEASE_DOCTYPES = {"PR"}
COMMUNICATED_DOCTYPES = {"HECOM", "HFCOM"}
COMMISSION_DECISION_DOCTYPES = {"HEDEC", "HFDEC"}
COMMUNICATED_BRANCHES = {"COMMUNICATEDCASES"}
COMMISSION_DECISION_BRANCHES = {"DECCOMMISSION", "ADMISSIBILITYCOM"}
INFO_NOTE_BRANCHES = {"CLIN"}

SOFT_SKIP_PARSER_MODES = {"info_note", "press_release"}

# Content-based fallback patterns for routing
CONTENT_ROUTING_PATTERNS = {
    "communicated_case": [
        r"(?:Communicated on|Communiqu[ée]e le)",
        r"OBJET\s+DE\s+L['\'\u2019]AFFAIRE",
    ],
    "information_note": [
        r"Information\s+Note\s+on\s+the\s+Court['\'\u2019]s\s+case-law",
        r"Note\s+d['\'\u2019]information\s+sur\s+la\s+jurisprudence\s+de\s+la\s+Cour",
    ],
    "press_release": [
        r"\bPress\s+release\b",
        r"\bCOMMUNIQUE\s+DE\s+PRESSE\b",
    ],
}

# ---------------------------------------------------------------------------
# Primary segmentation patterns
# ---------------------------------------------------------------------------
SEGMENTATION_PATTERNS = {
    # 1. PROCEDURE
    "procedure": [
        # Modern inline (after sentence-ending punctuation, followed by content)
        r"(?<=[\.)\s:])(?:THE\s+)?PROCEDURE(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        r"(?<=[\.)\s:])PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        r"(?<=[\.)\s:])FACTS\s+AND\s+PROCEDURE(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        # Standalone header line (optional Roman numeral prefix)
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:THE\s+)?PROCEDURE\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?FACTS\s+AND\s+PROCEDURE\s*(?:\n|$)",
        # Flattened text
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?(?:THE\s+)?PROCEDURE\b",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?PROCEDURE\s+AND\s+FACTS\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?FACTS\s+AND\s+PROCEDURE\s*(?:\n|$)",
        r"(?:^|[\n\r:_\.)]\s*)PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT\b",
        # Classic format
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?PROCEDURE(?:\s+AND\s+FACTS)?(?=[\s\d\n])",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?FACTS\s+AND\s+PROCEDURE(?=[\s\d\n])",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT(?=[\s\d\n])",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?THE\s+PROCEDURE(?=[\s\d\n])",
        # French
        r"(?<=[\.)\s:])(?:LA\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE(?=\d)",
        r"(?<=[\.)\s:])(?:LA\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE(?=[A-Z])",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:LA\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE\s*(?:\n|$)",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE(?=[\s\d\n])",
    ],
    # 2. THE FACTS / EN FAIT
    "facts": [
        # Modern inline
        r"(?<=[\.)\s:])THE\s+FACTS(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        r"\bTHE\s+FACTS\s*\d+\.",
        # Standalone header
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?THE\s+FACTS\s*(?:\n|$)",
        r"^[\ufeff\s]*(?:[IVX]+\.\s+)?THE\s+FACTS\s*(?:\n|$)",
        # Flattened text
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?THE\s+FACTS\b",
        # Alternative modern formats
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:THE\s+)?FACTS\s+OF\s+THE\s+CASE\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:THE\s+)?CIRCUMSTANCES\s+OF\s+THE\s+CASE\s*(?:\n|$)",
        # Classic formats
        r"(?:^|\n)\s*[IVX]+\.\s+THE\s+FACTS\b",
        r"(?:^|\n|:)\s*(?:PROCEDURE\s+AND\s+)?THE\s+FACTS(?=[\s\d\n])",
        r"AS\s+TO\s+THE\s+FACTS",
        r"(?:^|\n|:)\s*THE\s+CIRCUMSTANCES\s+OF\s+THE\s+CASE",
        # French
        r"(?<=[\.)\s:])EN\s+FAIT(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        r"\bEN\s+FAIT\s*\d+\.",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?EN\s+FAIT\s*(?:\n|$)",
        r"^[\ufeff\s]*(?:[IVX]+\.\s+)?EN\s+FAIT\s*(?:\n|$)",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?EN\s+FAIT\b",
        r"(?:^|\n)\s*[IVX]+\.\s+EN\s+FAIT\b",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?LES\s+FAITS(?=[\s\d\n])",
        r"LES\s+CIRCONSTANCES\s+DE\s+L['\'\u2019]AFFAIRE",
    ],
    # 3. COMPLAINTS / GRIEFS
    "complaints": [
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:THE\s+)?COMPLAINTS?\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?ALLEGED\s+VIOLATIONS?\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:THE\s+)?COMPLAINTS?(?=[\s\d\n])",
        r"(?:^|\n)\s*ALLEGED\s+VIOLATIONS?(?=[\s\d\n])",
        # French
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:LES\s+)?GRIEFS?\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:LES\s+)?GRIEFS?(?=[\s\d\n])",
        r"(?:^|\n)\s*VIOLATIONS?\s+ALLÉGUÉES?(?=[\s\d\n])",
        # Flattened text
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?(?:THE\s+)?COMPLAINTS?\b",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?LES\s+GRIEFS?\b",
    ],
    # 4. THE LAW / EN DROIT
    "law": [
        # Modern inline
        r'(?<=[\.)\s:"\u201d\u201c])THE\s+LAW(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]|\n))',
        r'(?<=[\.)\s:"\u201d\u201c])AS\s+TO\s+THE\s+LAW(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]|\n))',
        r"(?<=[\.)\s:])THE\s+LAW(?=\s*[:—–-]?\s*\n)",
        # Standalone header
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?THE\s+LAW\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?AS\s+TO\s+THE\s+LAW\s*(?:\n|$)",
        # Flattened text
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?THE\s+LAW\b",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?AS\s+TO\s+THE\s+LAW\b",
        # Word boundary
        r"\bTHE\s+LAW\b(?![a-z])",
        r"\bAS\s+TO\s+THE\s+LAW\b(?![a-z])",
        # RELEVANT LEGAL FRAMEWORK
        r"(?:^|\n)\s*RELEVANT\s+LEGAL\s+FRAMEWORK(?:\s+AND\s+PRACTICE)?(?=\s|$|\d|[IVX]+|[:—–-])",
        r'(?:^|[\n\r:_\.)"]\s*)RELEVANT\s+LEGAL\s+FRAMEWORK(?:\s+AND\s+PRACTICE)?(?=\s|$|\d|[IVX]+|[:—–-])',
        # French
        r"(?<=[\.)\s:])EN\s+DROIT(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]|\n))",
        r"(?<=[\.)\s:])EN\s+DROIT(?=\s*[:—–-]?\s*\n)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?EN\s+DROIT\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?LE\s+DROIT\s*(?:\n|$)",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?EN\s+DROIT\b",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?LE\s+DROIT\b",
        r"\bEN\s+DROIT\b(?![a-z])",
        r"\bLE\s+DROIT\b(?![a-z])",
        r"\bSUR\s+LE\s+DROIT\b(?![a-z])",
    ],
    # 5. OPERATIVE (FOR THESE REASONS)
    "operative": [
        r"FOR\s+THESE\s+REASONS",
        r"FOR\s+THE(?:SE)?\s+(?:ABOVE|FOREGOING)?\s*REASONS",
        r"Now\s+therefore\s+the\s+(?:Court|Commission)",
        # French
        r"PAR\s+CES\s+MOTIFS",
        r"POUR\s+CES\s+MOTIFS",
    ],
    # 6. SEPARATE OPINION(S)
    "separate_opinion": [
        r"(?i)(?:^|[\n\r:_\.)]\s*)SEPARATE\s+OPINIONS?(?:\s+OF)?",
        r"(?i)(?:^|[\n\r:_\.)]\s*)SEPARATE\s+JOINT\s+CONCURRING\s+OPINION",
        r"(?i)(?:^|[\n\r:_\.)]\s*)(?:CONCURRING|DISSENTING|PARTLY\s+DISSENTING)\s+OPINION",
        # French
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINIONS?\s+S[ÉE]PAR[ÉE]ES?(?:\s+SUIVANTES)?",
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINION\s+(?:CONCORDANTE|DISSIDENTE|PARTIELLEMENT\s+DISSIDENTE)",
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINION\s+S[ÉE]PAR[ÉE]E(?:\s+CONCORDANTE|\s+DISSIDENTE)?",
    ],
    # 7. APPENDIX / ANNEXE
    "appendix": [
        r"(?:^|[\n\r:_\.)]\s*)APPENDIX(?=\s*(?:\n|$|[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z])))",
        r"(?:^|[\n\r:_\.)]\s*)ANNEX(?=\s*(?:\n|$|[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z])))",
        # Inline after double-space separator
        r'(?:^|[\n\r:_\.)"]\s*|\s{2,})APPENDIX(?=\s*(?:\n|$|[A-Z]))',
        r'(?:^|[\n\r:_\.)"]\s*|\s{2,})ANNEX(?=\s*(?:\n|$|[A-Z]))',
        # French
        r"(?:^|[\n\r:_\.)]\s*)ANNEXE(?=\s*(?:\n|$|[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z])))",
        r'(?:^|[\n\r:_\.)"]\s*|\s{2,})ANNEXE(?=\s*(?:\n|$|[A-Z]))',
    ],
    # 8. SUBJECT MATTER (Committee judgments)
    "subject_matter": [
        r"(?:^|\n)\s*SUBJECT\s+MATTER\s+OF\s+THE\s+CASE\s*(?:\n|$)",
        r"(?<=[\.)\s:])SUBJECT\s+MATTER\s+OF\s+THE\s+CASE(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
    ],
    # 9. THE COURT'S ASSESSMENT (Committee judgments)
    "court_assessment": [
        r"(?:^|\n)\s*THE\s+COURT['\u2019\u2018]S\s+ASSESSMENT\s*(?:\n|$)",
        r"(?<=[\.)\s:])THE\s+COURT['\u2019\u2018]S\s+ASSESSMENT(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
    ],
}

# ---------------------------------------------------------------------------
# Nonstandard fallback patterns
# ---------------------------------------------------------------------------
NONSTANDARD_SEGMENTATION_PATTERNS = {
    "communicated_case": {
        "procedure": [
            r"(?:^|\n)\s*(?:THE\s+)?PROCEDURE\s*(?:\n|$)",
            r"(?:^|\n)\s*(?:LA\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE\s*(?:\n|$)",
            r"(?:^|\n)\s*PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT\s*(?:\n|$)",
        ],
        "facts": [
            r"(?:^|\n)\s*(?:THE\s+)?FACTS?\s*(?:\n|$)",
            r"(?:^|\n)\s*EN\s+FAIT\s*(?:\n|$)",
            r"(?:^|\n)\s*LES\s+FAITS?\s*(?:\n|$)",
            r"(?:^|\n)\s*SUBJECT\s+MATTER\s+OF\s+THE\s+CASES?\s*(?:\n|$)",
            r"(?:^|\n)\s*OBJET\s+DE\s+L['\'\u2019]AFFAIRE\s*(?:\n|$)",
        ],
        "complaints": [
            r"(?:^|\n)\s*(?:THE\s+)?COMPLAINTS?\s*(?:\n|$)",
            r"(?:^|\n)\s*GRIEFS?\s*(?:\n|$)",
            r"(?:^|\n)\s*ALLEGED\s+VIOLATIONS?\s*(?:\n|$)",
        ],
        "law": [
            r"(?:^|\n)\s*(?:THE\s+)?LAW\s*(?:\n|$)",
            r"(?:^|\n)\s*EN\s+DROIT\s*(?:\n|$)",
            r"(?:^|\n)\s*QUESTIONS?\s+TO\s+THE\s+PARTIES\s*(?:\n|$)",
            r"(?:^|\n)\s*QUESTIONS?\s+AUX\s+PARTIES\s*(?:\n|$)",
            r"(?:^|\n)\s*RELEVANT\s+LEGAL\s+FRAMEWORK(?:\s+AND\s+PRACTICE)?\s*(?:\n|$)",
        ],
        "subject_matter": [
            r"(?:^|\n)\s*SUBJECT\s+MATTER\s+OF\s+THE\s+CASES?\s*(?:\n|$)",
            r"(?:^|\n)\s*OBJET\s+DE\s+L['\'\u2019]AFFAIRE\s*(?:\n|$)",
        ],
        "appendix": [
            r"(?:^|\n)\s*APPENDIX\s*(?:\n|$)",
            r"(?:^|\n)\s*ANNEXE?\s*(?:\n|$)",
        ],
        "separate_opinion": [
            r"(?:^|\n)\s*SEPARATE\s+OPINIONS?\s*(?:\n|$)",
            r"(?:^|\n)\s*OPINIONS?\s+S[ÉE]PAR[ÉE]ES?\s*(?:\n|$)",
        ],
    },
    "commission_decision": {
        "procedure": [
            r"(?:^|\n)\s*(?:THE\s+)?PROCEDURE\s*(?:\n|$)",
            r"(?:^|\n)\s*(?:LA\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE\s*(?:\n|$)",
            r"(?:^|\n)\s*PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT\s*(?:\n|$)",
        ],
        "facts": [
            r"(?:^|\n)\s*(?:THE\s+)?FACTS\s*(?:\n|$)",
            r"(?:^|\n)\s*AS\s+TO\s+THE\s+FACTS\s*(?:\n|$)",
            r"(?:^|\n)\s*EN\s+FAIT\s*(?:\n|$)",
            r"(?:^|\n)\s*LES\s+FAITS\s*(?:\n|$)",
        ],
        "law": [
            r"(?:^|\n)\s*(?:THE\s+)?LAW\s*(?:\n|$)",
            r"(?:^|\n)\s*AS\s+TO\s+THE\s+LAW\s*(?:\n|$)",
            r"(?:^|\n)\s*EN\s+DROIT\s*(?:\n|$)",
            r"(?:^|\n)\s*LE\s+DROIT\s*(?:\n|$)",
            r"(?:^|\n)\s*SUR\s+LE\s+DROIT\s*(?:\n|$)",
            r"(?:^|\n)\s*RELEVANT\s+LEGAL\s+FRAMEWORK(?:\s+AND\s+PRACTICE)?\s*(?:\n|$)",
        ],
        "complaints": [
            r"(?:^|\n)\s*(?:THE\s+)?COMPLAINTS?\s*(?:\n|$)",
            r"(?:^|\n)\s*GRIEFS?\s*(?:\n|$)",
        ],
        "operative": [
            r"(?:^|\n)\s*FOR\s+THESE\s+REASONS\s*(?:\n|$)",
            r"(?:^|\n)\s*PAR\s+CES\s+MOTIFS\s*(?:\n|$)",
            r"(?:^|\n)\s*POUR\s+CES\s+MOTIFS\s*(?:\n|$)",
        ],
        "appendix": [
            r"(?:^|\n)\s*APPENDIX\s*(?:\n|$)",
            r"(?:^|\n)\s*ANNEXE?\s*(?:\n|$)",
        ],
        "separate_opinion": [
            r"(?:^|\n)\s*SEPARATE\s+OPINIONS?\s*(?:\n|$)",
            r"(?:^|\n)\s*OPINIONS?\s+S[ÉE]PAR[ÉE]ES?\s*(?:\n|$)",
        ],
    },
}

# ---------------------------------------------------------------------------
# Pattern compilation
# ---------------------------------------------------------------------------
_IGNORECASE_SECTIONS = {
    "operative",
    "court_assessment",
    "procedure",
    "facts",
    "complaints",
    "law",
    "appendix",
    "separate_opinion",
}


def _compile_patterns(raw_patterns):
    """Compile raw regex pattern strings into compiled pattern objects.

    :param dict raw_patterns: Mapping of section names to lists of regex strings.
    :return: Dict mapping section names to lists of compiled regex patterns.
    """
    compiled = {}
    for section, patterns in raw_patterns.items():
        if section in _IGNORECASE_SECTIONS:
            compiled[section] = [
                re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns
            ]
        else:
            # subject_matter: no IGNORECASE — patterns are already uppercase
            compiled[section] = [re.compile(p, re.MULTILINE) for p in patterns]
    return compiled


def _compile_nonstandard_patterns(raw_nonstandard):
    """Compile nonstandard fallback patterns.

    :param dict raw_nonstandard: Mapping of parser_mode -> section -> pattern list.
    :return: Dict of parser_mode -> section -> compiled pattern list.
    """
    compiled = {}
    for parser_mode, section_map in raw_nonstandard.items():
        compiled[parser_mode] = {}
        for section, patterns in section_map.items():
            compiled[parser_mode][section] = [
                re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns
            ]
    return compiled


# Module-level compiled patterns (compiled once at import time)
_COMPILED_PATTERNS = _compile_patterns(SEGMENTATION_PATTERNS)
_COMPILED_NONSTANDARD = _compile_nonstandard_patterns(NONSTANDARD_SEGMENTATION_PATTERNS)


# ---------------------------------------------------------------------------
# Parser mode routing
# ---------------------------------------------------------------------------
def normalize_meta_value(value) -> str:
    """Normalize metadata values for stable comparisons.

    Handles None, NaN, and whitespace. Returns uppercase string or empty string.
    """
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if not text else text.upper()


def _detect_content_routing(text: str) -> Optional[str]:
    """Content-based fallback for parser routing.

    Only checks the 3 document families that require non-standard handling.

    :param str text: The full text of the document.
    :return: The matching family key, or None if no match.
    """
    for family, patterns in CONTENT_ROUTING_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return family
    return None


def choose_parser_mode(
    text: str,
    metadata_doctype: Optional[str] = None,
    metadata_doctypebranch: Optional[str] = None,
) -> str:
    """Choose parser mode from metadata columns, falling back to content detection.

    Priority:
      1. Metadata doctype/doctypebranch (fast, reliable when present)
      2. Content-based regex scan (fallback when metadata is absent)
      3. Default to 'standard'

    :param str text: The full text of the document.
    :param str metadata_doctype: The HUDOC doctype value.
    :param str metadata_doctypebranch: The HUDOC doctypebranch value.
    :return: Parser mode string.
    """
    doctype = normalize_meta_value(metadata_doctype)
    doctypebranch = normalize_meta_value(metadata_doctypebranch)

    # Metadata-based routing (checked first)
    if doctype in INFO_NOTE_DOCTYPES or doctypebranch in INFO_NOTE_BRANCHES:
        return "info_note"
    if doctype in PRESS_RELEASE_DOCTYPES:
        return "press_release"
    if doctype in COMMUNICATED_DOCTYPES or doctypebranch in COMMUNICATED_BRANCHES:
        return "communicated_case"
    if (
        doctype in COMMISSION_DECISION_DOCTYPES
        or doctypebranch in COMMISSION_DECISION_BRANCHES
    ):
        return "commission_decision"

    # Content-based fallback (only if metadata didn't match)
    content_family = _detect_content_routing(text)
    if content_family == "information_note":
        return "info_note"
    if content_family == "press_release":
        return "press_release"
    if content_family == "communicated_case":
        return "communicated_case"

    return "standard"


# ---------------------------------------------------------------------------
# Boundary-finding algorithm
# ---------------------------------------------------------------------------
def find_section_boundaries(text, compiled_patterns, original_text=None):
    """Find all section header positions in text.

    Uses a two-pass approach:
      Pass 1 (pre-scan): identify which sections have a "strong header" match.
      Pass 2 (main scan): find all matches, apply validation filters, collect
        boundary tuples.

    After both passes, applies a proximity filter to remove spurious
    micro-segments.

    :param str text: The normalized text (underscores replaced with spaces).
    :param dict compiled_patterns: Section -> list of compiled regex patterns.
    :param str original_text: The original un-normalized text for validation.
    :return: Sorted list of (section, start_pos, end_pos, matched_text) tuples.
    """
    uppercase_only_sections = {
        "procedure",
        "facts",
        "law",
        "complaints",
        "subject_matter",
    }
    header_position_sections = {
        "procedure",
        "facts",
        "complaints",
        "law",
        "appendix",
        "separate_opinion",
    }

    # --- Nested validation functions ---
    def is_header_like(start_pos, end_pos):
        base_text = original_text if original_text is not None else text
        prefix_start = base_text.rfind("\n", 0, start_pos) + 1
        prefix = base_text[prefix_start:start_pos]
        suffix = base_text[end_pos : end_pos + 20]
        before = base_text[max(0, start_pos - 5) : start_pos]

        # If the match itself starts with a newline, it's line-anchored
        if start_pos < len(base_text) and base_text[start_pos] == "\n":
            before_ok = True
        else:
            before_ok = prefix.strip() == "" or bool(
                re.search(r'[\n\r\.\):;_\-–—""]\s*$', before)
            )
        if (
            not before_ok
            and start_pos < len(base_text)
            and base_text[start_pos] in {".", ":", ")", ";", '"', "\u201d"}
        ):
            before_ok = True
        if not before_ok:
            if re.search(r"_{3,}\s*$", prefix) or re.search(r"\s{5,}$", prefix):
                before_ok = True
        if not before_ok:
            return False

        return bool(
            re.match(
                r"[\s:—–\-]*\d|[\s:—–\-]*\n|[\s:—–\-]*[IVX]+\."
                r"|[\s:—–\-]*[A-Z]|[\s:—–\-]*[\(\[]",
                suffix,
            )
        )

    def is_strong_header(section, matched_text):
        mt = matched_text.upper()
        if section == "law":
            return any(
                k in mt
                for k in [
                    "THE LAW",
                    "AS TO THE LAW",
                    "EN DROIT",
                    "LE DROIT",
                    "SUR LE DROIT",
                    "RELEVANT LEGAL FRAMEWORK",
                ]
            )
        if section == "facts":
            return any(
                k in mt
                for k in [
                    "THE FACTS",
                    "EN FAIT",
                    "LES FAITS",
                    "CIRCUMSTANCES OF THE CASE",
                ]
            )
        if section == "procedure":
            return bool(
                re.search(r"PROCEDURE|PROCEEDING|PROC(?:É|E\u0301|é|e\u0301)DURE", mt)
            )
        if section == "complaints":
            return any(k in mt for k in ["COMPLAINT", "GRIEF", "ALLEGED VIOLATION"])
        if section == "separate_opinion":
            return "OPINION" in mt
        if section == "appendix":
            return any(k in mt for k in ["APPENDIX", "ANNEXE", "ANNEX"])
        if section == "operative":
            return any(
                k in mt
                for k in [
                    "FOR THESE REASONS",
                    "PAR CES MOTIFS",
                    "POUR CES MOTIFS",
                ]
            )
        if section == "court_assessment":
            return "COURT" in mt and "ASSESSMENT" in mt
        if section == "subject_matter":
            return "SUBJECT MATTER" in mt
        return False

    def has_initials_prefix(start_pos):
        base_text = original_text if original_text is not None else text
        prefix = base_text[max(0, start_pos - 60) : start_pos]
        if not prefix:
            return False
        cleaned = re.sub(r"[\u2010-\u2015-]", ".", prefix)
        cleaned = cleaned.replace(" ", "")
        cleaned = re.sub(r"\.+", ".", cleaned)
        return re.search(r"(?:[A-Z]\.){2,}[A-Z]?$", cleaned) is not None

    def is_appendix_inline_header(start_pos, end_pos, matched_text):
        base_text = original_text if original_text is not None else text
        prefix_start = base_text.rfind("\n", 0, start_pos) + 1
        prefix = base_text[prefix_start:start_pos]
        if not (re.search(r"\s{2,}$", prefix) or re.match(r"^\s{2,}", matched_text)):
            return False
        if re.search(r"[a-z]", matched_text):
            return False
        suffix = base_text[end_pos : end_pos + 20]
        return bool(re.match(r"[A-Z]", suffix))

    # --- Pass 1: pre-scan for strong headers ---
    strong_sections = set()
    for section, patterns in compiled_patterns.items():
        for pat in patterns:
            for m in pat.finditer(text):
                if is_strong_header(section, m.group()):
                    strong_sections.add(section)
                    break
            if section in strong_sections:
                break

    # Collect all LAW header positions for complaints disambiguation
    law_positions = []
    for pat in compiled_patterns.get("law", []):
        for m in pat.finditer(text):
            law_positions.append(m.start())

    # --- Pass 2: main scan ---
    boundaries = []
    seen_positions = set()

    for section, patterns in compiled_patterns.items():
        for pat in patterns:
            for m in pat.finditer(text):
                start_pos = m.start()
                end_pos = m.end()
                matched_text = m.group()

                # Position dedup
                if start_pos in seen_positions:
                    continue

                # Uppercase-only section filter
                if section in uppercase_only_sections:
                    if re.search(r"[a-z]", matched_text):
                        base_text = original_text if original_text is not None else text
                        prefix_start = base_text.rfind("\n", 0, start_pos) + 1
                        prefix = base_text[prefix_start:start_pos]
                        if not (
                            re.search(r"_{3,}\s*$", prefix)
                            or re.search(r"\s{5,}$", prefix)
                        ):
                            continue
                    # Verify canonical keyword
                    if not is_strong_header(section, matched_text):
                        continue

                # Complaints disambiguation
                if section == "complaints":
                    mt_upper = matched_text.upper()
                    # Check extended text beyond match for "OF ARTICLE"
                    # because the regex may only capture "ALLEGED VIOLATION"
                    # while "OF ARTICLE ..." follows immediately after.
                    extended_upper = (
                        matched_text + text[end_pos : end_pos + 40]
                    ).upper()
                    if re.search(r"ALLEGED\s+VIOLATION\s+OF\s+ARTICLE", extended_upper):
                        continue
                    if "ALLEGED VIOLATION" in mt_upper:
                        near_law = any(
                            abs(start_pos - lp) < 350 for lp in law_positions
                        )
                        if near_law:
                            continue
                    if not is_header_like(start_pos, end_pos):
                        continue

                # Court assessment filter
                if section == "court_assessment":
                    mt_upper = matched_text.upper()
                    if not ("COURT" in mt_upper and "ASSESSMENT" in mt_upper):
                        continue
                    base_text = original_text if original_text is not None else text
                    before = base_text[max(0, start_pos - 5) : start_pos]
                    prefix_start = base_text.rfind("\n", 0, start_pos) + 1
                    prefix = base_text[prefix_start:start_pos]
                    if prefix.strip() != "" and not re.search(r"[\.\):]\s*$", before):
                        continue

                # Header position check
                if section in header_position_sections:
                    if not is_header_like(start_pos, end_pos):
                        # Exceptions
                        if section == "separate_opinion" and has_initials_prefix(
                            start_pos
                        ):
                            pass  # allowed
                        elif section == "appendix" and is_appendix_inline_header(
                            start_pos, end_pos, matched_text
                        ):
                            pass  # allowed
                        else:
                            continue

                # Strong header suppression
                if section in strong_sections and not is_strong_header(
                    section, matched_text
                ):
                    # Exception: keep RELEVANT LEGAL FRAMEWORK even if THE LAW
                    if (
                        section == "law"
                        and "RELEVANT LEGAL FRAMEWORK" in matched_text.upper()
                    ):  # pragma: no cover
                        pass  # pragma: no cover
                    else:
                        continue

                seen_positions.add(start_pos)
                boundaries.append((section, start_pos, end_pos, matched_text))

    # --- Post-processing: proximity filter ---
    boundaries.sort(key=lambda x: x[1])
    filtered = []
    last_pos = -1000
    last_section = None
    for boundary in boundaries:
        section, pos, _, matched_text = boundary
        if pos - last_pos >= 100:
            filtered.append(boundary)
            last_pos = pos
            last_section = section
        else:
            if section != last_section and is_strong_header(section, matched_text):
                filtered.append(boundary)
                last_pos = pos
                last_section = section

    return filtered


# ---------------------------------------------------------------------------
# Segment extraction
# ---------------------------------------------------------------------------
def extract_segments_from_boundaries(text, boundaries, min_segment_length=50):
    """Extract text segments from boundary positions.

    For each boundary, extracts text from that boundary's start position to the
    next boundary's start position (or end of text). If the same section appears
    multiple times, concatenates with double newline.

    :param str text: The full document text.
    :param list boundaries: Sorted list of (section, start, end, matched_text).
    :param int min_segment_length: Minimum chars for a segment to be kept.
    :return: Dict mapping section names to extracted text strings.
    """
    if not boundaries:
        return {}

    segments = {}
    for i, (section, start, end, matched_text) in enumerate(boundaries):
        if i + 1 < len(boundaries):
            next_start = boundaries[i + 1][1]
            section_text = text[start:next_start].strip()
        else:
            section_text = text[start:].strip()

        if len(section_text) < min_segment_length:
            continue

        if section in segments:
            segments[section] += "\n\n" + section_text
        else:
            segments[section] = section_text

    return segments


# ---------------------------------------------------------------------------
# Nonstandard segmentation (relaxed patterns)
# ---------------------------------------------------------------------------
def _segment_text_nonstandard(text, compiled_ns_patterns, min_segment_length=35):
    """Segment using nonstandard (relaxed) patterns.

    Used as fallback for communicated_case and commission_decision modes
    when primary patterns find nothing.

    :param str text: The full document text.
    :param dict compiled_ns_patterns: Section -> compiled pattern list.
    :param int min_segment_length: Minimum segment length.
    :return: Dict mapping section names to extracted text.
    """
    normalized_text = text.replace("_", " ")
    boundaries = []
    seen_positions = set()

    for section, patterns in compiled_ns_patterns.items():
        for pat in patterns:
            for m in pat.finditer(normalized_text):
                start_pos = m.start()
                if start_pos not in seen_positions:
                    seen_positions.add(start_pos)
                    boundaries.append((section, start_pos, m.end(), m.group()))

    boundaries.sort(key=lambda x: x[1])
    return extract_segments_from_boundaries(text, boundaries, min_segment_length)


# ---------------------------------------------------------------------------
# Main segmentation function
# ---------------------------------------------------------------------------
def segment_echr_texts(
    df: pd.DataFrame,
    allowed_langs: Tuple[str, ...] = ("ENG", "FRE"),
    min_segment_length: int = 50,
    max_text_length: int = 5_000_000,
) -> pd.DataFrame:
    """Segment ECHR full texts into structured legal sections.

    :param pd.DataFrame df: Input DataFrame. Required columns: itemid,
        languageisocode, fulltext. Optional columns: ecli, doctype,
        doctypebranch.
    :param tuple allowed_langs: Only process rows whose languageisocode is
        in this set. Other rows are returned with segments as None and
        parser_mode = 'skipped_language'.
    :param int min_segment_length: Minimum character length for a segment
        to be kept (default: 50).
    :param int max_text_length: Safety limit. Texts longer than this are
        skipped (default: 5,000,000).
    :return: DataFrame with one row per input row. Columns: itemid,
        languageisocode, ecli, parser_mode, procedure, facts, complaints,
        law, operative, subject_matter, court_assessment, separate_opinion,
        appendix, num_sections, error.
    :raises ValueError: If required columns are missing.
    """
    # Input validation
    required_cols = {"itemid", "languageisocode", "fulltext"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    if df.empty:
        cols = (
            ["itemid", "languageisocode", "ecli", "parser_mode"]
            + SECTION_NAMES
            + ["num_sections", "error"]
        )
        return pd.DataFrame(columns=cols)

    has_ecli = "ecli" in df.columns
    has_doctype = "doctype" in df.columns
    has_doctypebranch = "doctypebranch" in df.columns

    results = []
    for row in df.itertuples(index=False):
        result = {
            "itemid": row.itemid,
            "languageisocode": row.languageisocode,
            "ecli": getattr(row, "ecli", None) if has_ecli else None,
        }

        try:
            lang = normalize_meta_value(row.languageisocode)

            # Skip disallowed languages
            if lang not in {l.upper() for l in allowed_langs}:
                result["parser_mode"] = "skipped_language"
                for s in SECTION_NAMES:
                    result[s] = None
                result["num_sections"] = 0
                result["error"] = None
                results.append(result)
                continue

            fulltext = row.fulltext

            # Skip missing/empty text
            if not fulltext or not isinstance(fulltext, str):
                result["parser_mode"] = "standard"
                for s in SECTION_NAMES:
                    result[s] = None
                result["num_sections"] = 0
                result["error"] = "Missing or empty fulltext"
                results.append(result)
                continue

            # Skip oversized text
            if len(fulltext) > max_text_length:
                result["parser_mode"] = "standard"
                for s in SECTION_NAMES:
                    result[s] = None
                result["num_sections"] = 0
                result["error"] = f"Text too long ({len(fulltext)} chars)"
                logger.warning(
                    "Skipping %s: text too long (%d chars)",
                    row.itemid,
                    len(fulltext),
                )
                results.append(result)
                continue

            # Stage 1: Route parser mode
            doctype = getattr(row, "doctype", None) if has_doctype else None
            doctypebranch = (
                getattr(row, "doctypebranch", None) if has_doctypebranch else None
            )
            parser_mode = choose_parser_mode(fulltext, doctype, doctypebranch)
            result["parser_mode"] = parser_mode

            # Stage 2 & 3: Find boundaries and extract
            if parser_mode in SOFT_SKIP_PARSER_MODES:
                segments = {}
            elif parser_mode == "standard":
                normalized = fulltext.replace("_", " ")
                boundaries = find_section_boundaries(
                    normalized, _COMPILED_PATTERNS, original_text=fulltext
                )
                segments = extract_segments_from_boundaries(
                    fulltext, boundaries, min_segment_length
                )
            elif parser_mode in ("communicated_case", "commission_decision"):
                # Try strict patterns first
                normalized = fulltext.replace("_", " ")
                boundaries = find_section_boundaries(
                    normalized, _COMPILED_PATTERNS, original_text=fulltext
                )
                segments = extract_segments_from_boundaries(
                    fulltext, boundaries, min_segment_length
                )
                if not segments:
                    # Fall back to relaxed nonstandard patterns
                    ns_patterns = _COMPILED_NONSTANDARD.get(parser_mode, {})
                    if ns_patterns:
                        segments = _segment_text_nonstandard(
                            fulltext, ns_patterns, min_segment_length=35
                        )
            else:
                # Unknown mode — treat as standard
                normalized = fulltext.replace("_", " ")
                boundaries = find_section_boundaries(
                    normalized, _COMPILED_PATTERNS, original_text=fulltext
                )
                segments = extract_segments_from_boundaries(
                    fulltext, boundaries, min_segment_length
                )

            # Fill section columns
            for s in SECTION_NAMES:
                result[s] = segments.get(s)
            result["num_sections"] = sum(
                1 for s in SECTION_NAMES if result[s] is not None
            )

            # Determine error
            if segments:
                result["error"] = None
            elif parser_mode in SOFT_SKIP_PARSER_MODES:
                result["error"] = None
            else:
                result["error"] = "No sections found in text"

        except Exception as e:
            logger.error(
                "Segmentation failed for %s: %s",
                result.get("itemid", "unknown"),
                e,
            )
            result["parser_mode"] = result.get("parser_mode", "standard")
            for s in SECTION_NAMES:
                result[s] = None
            result["num_sections"] = 0
            result["error"] = str(e)

        results.append(result)

    output_cols = (
        ["itemid", "languageisocode", "ecli", "parser_mode"]
        + SECTION_NAMES
        + ["num_sections", "error"]
    )
    return pd.DataFrame(results, columns=output_cols)
