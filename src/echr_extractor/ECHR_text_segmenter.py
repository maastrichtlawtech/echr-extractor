"""ECHR full-text segmentation into structured legal sections.

This module contains the hardened regex-based segmentation engine used to
split ECHR full texts into legal sections. It is aligned with the
battle-tested implementation in the companion `echr` repository while
retaining the extractor package's DataFrame-oriented public contract.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


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


DOCUMENT_TYPE_PATTERNS = {
    "committee": [
        r"sitting as a Committee composed of",
        r"SUBJECT\s+MATTER\s+OF\s+THE\s+CASE",
    ],
    "article_50": [
        r"\(Article\s+50\)",
        r"APPLICATION\s+OF\s+ARTICLE\s+50",
    ],
    "admissibility": [
        r"DECISION\s+AS\s+TO\s+THE\s+ADMISSIBILITY",
        r"declares?\s+the\s+application\s+inadmissible",
    ],
    "advisory": [
        r"ADVISORY\s+OPINION",
        r"REQUEST\s+FOR\s+AN\s+ADVISORY\s+OPINION",
    ],
    "communicated_case": [
        r"(?:Communicated on|Communiqu[ée]e le)",
        r"OBJET\s+DE\s+L['’]AFFAIRE",
    ],
    "information_note": [
        r"Information\s+Note\s+on\s+the\s+Court['’]s\s+case-law",
        r"Note\s+d['’]information\s+sur\s+la\s+jurisprudence\s+de\s+la\s+Cour",
    ],
    "press_release": [
        r"\bPress\s+release\b",
        r"\bCOMMUNIQUE\s+DE\s+PRESSE\b",
    ],
}

CONTENT_ROUTING_PATTERNS = {
    key: DOCUMENT_TYPE_PATTERNS[key]
    for key in ("communicated_case", "information_note", "press_release")
}

INFO_NOTE_DOCTYPES = {"CLIN", "CLINF"}
PRESS_RELEASE_DOCTYPES = {"PR"}
COMMUNICATED_DOCTYPES = {"HECOM", "HFCOM"}
COMMISSION_DECISION_DOCTYPES = {"HEDEC", "HFDEC"}
COMMUNICATED_BRANCHES = {"COMMUNICATEDCASES"}
COMMISSION_DECISION_BRANCHES = {"DECCOMMISSION", "ADMISSIBILITYCOM"}
INFO_NOTE_BRANCHES = {"CLIN"}

SOFT_SKIP_PARSER_MODES = {"info_note", "press_release"}

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
            r"(?:^|\n)\s*OBJET\s+DE\s+L['’]AFFAIRE\s*(?:\n|$)",
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
            r"(?:^|\n)\s*OBJET\s+DE\s+L['’]AFFAIRE\s*(?:\n|$)",
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

SEGMENTATION_PATTERNS = {
    "procedure": [
        r"(?<=[\.)\s:])(?:THE\s+)?PROCEDURE(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        r"(?<=[\.)\s:])PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        r"(?<=[\.)\s:])FACTS\s+AND\s+PROCEDURE(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:THE\s+)?PROCEDURE\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?FACTS\s+AND\s+PROCEDURE\s*(?:\n|$)",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?(?:THE\s+)?PROCEDURE\b",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?PROCEDURE\s+AND\s+FACTS\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?FACTS\s+AND\s+PROCEDURE\s*(?:\n|$)",
        r"(?:^|[\n\r:_\.)]\s*)PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT\b",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?PROCEDURE(?:\s+AND\s+FACTS)?(?=[\s\d\n])",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?FACTS\s+AND\s+PROCEDURE(?=[\s\d\n])",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?PROCEEDINGS\s+BEFORE\s+THE\s+COMMISSION\s+AND\s+THE\s+COURT(?=[\s\d\n])",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?THE\s+PROCEDURE(?=[\s\d\n])",
        r"(?<=[\.)\s:])(?:LA\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE(?=\d)",
        r"(?<=[\.)\s:])(?:LA\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE(?=[A-Z])",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:LA\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE\s*(?:\n|$)",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?PROC(?:É|E\u0301|é|e\u0301)DURE(?=[\s\d\n])",
    ],
    "facts": [
        r"(?<=[\.)\s:])THE\s+FACTS(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        r"\bTHE\s+FACTS\s*\d+\.",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?THE\s+FACTS\s*(?:\n|$)",
        r"^[\ufeff\s]*(?:[IVX]+\.\s+)?THE\s+FACTS\s*(?:\n|$)",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?THE\s+FACTS\b",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:THE\s+)?FACTS\s+OF\s+THE\s+CASE\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:THE\s+)?CIRCUMSTANCES\s+OF\s+THE\s+CASE\s*(?:\n|$)",
        r"(?:^|\n)\s*[IVX]+\.\s+THE\s+FACTS\b",
        r"(?:^|\n|:)\s*(?:PROCEDURE\s+AND\s+)?THE\s+FACTS(?=[\s\d\n])",
        r"AS\s+TO\s+THE\s+FACTS",
        r"(?:^|\n|:)\s*THE\s+CIRCUMSTANCES\s+OF\s+THE\s+CASE",
        r"(?<=[\.)\s:])EN\s+FAIT(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
        r"\bEN\s+FAIT\s*\d+\.",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?FAITS\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?EN\s+FAIT\s*(?:\n|$)",
        r"^[\ufeff\s]*(?:[IVX]+\.\s+)?EN\s+FAIT\s*(?:\n|$)",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?FAITS\b",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?EN\s+FAIT\b",
        r"(?:^|\n)\s*[IVX]+\.\s+EN\s+FAIT\b",
        r"(?:^|\n|:)\s*(?:[IVX]+\.\s+)?LES\s+FAITS(?=[\s\d\n])",
        r"LES\s+CIRCONSTANCES\s+DE\s+L['’]AFFAIRE",
        r"LES\s+CIRCONSTANCES\s+DE\s+L['’]ESP[ÈEÉ]CE",
    ],
    "complaints": [
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:THE\s+)?COMPLAINTS?\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?ALLEGED\s+VIOLATIONS?\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:THE\s+)?COMPLAINTS?(?=[\s\d\n])",
        r"(?:^|\n)\s*ALLEGED\s+VIOLATIONS?(?=[\s\d\n])",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?(?:LES\s+)?GRIEFS?\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:LES\s+)?GRIEFS?(?=[\s\d\n])",
        r"(?:^|\n)\s*VIOLATIONS?\s+ALLÉGUÉES?(?=[\s\d\n])",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?(?:THE\s+)?COMPLAINTS?\b",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?LES\s+GRIEFS?\b",
    ],
    "law": [
        r'(?<=[\.)\s:"\u201d\u201c])THE\s+LAW(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]|\n))',
        r'(?<=[\.)\s:"\u201d\u201c])AS\s+TO\s+THE\s+LAW(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]|\n))',
        r"(?<=[\.)\s:])THE\s+LAW(?=\s*[:—–-]?\s*\n)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?THE\s+LAW\s*(?:\n|$)",
        r"(?:^|\n)\s*(?:[IVX]+\.\s+)?AS\s+TO\s+THE\s+LAW\s*(?:\n|$)",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?THE\s+LAW\b",
        r"(?:^|[\n\r:_\.)]\s*)(?:[IVX]+\.\s+)?AS\s+TO\s+THE\s+LAW\b",
        r"\bTHE\s+LAW\b(?![a-z])",
        r"\bAS\s+TO\s+THE\s+LAW\b(?![a-z])",
        r"(?:^|\n)\s*RELEVANT\s+LEGAL\s+FRAMEWORK(?:\s+AND\s+PRACTICE)?(?=\s|$|\d|[IVX]+|[:—–-])",
        r'(?:^|[\n\r:_\.)"]\s*)RELEVANT\s+LEGAL\s+FRAMEWORK(?:\s+AND\s+PRACTICE)?(?=\s|$|\d|[IVX]+|[:—–-])',
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
    "operative": [
        r"FOR\s+THESE\s+REASONS",
        r"FOR\s+THE(?:SE)?\s+(?:ABOVE|FOREGOING)?\s*REASONS",
        r"Now\s+therefore\s+the\s+(?:Court|Commission)",
        r"PAR\s+CES\s+MOTIFS",
        r"POUR\s+CES\s+MOTIFS",
    ],
    "separate_opinion": [
        r"(?i)(?:^|[\n\r:_\.)]\s*)SEPARATE\s+OPINIONS?(?:\s+OF)?",
        r"(?i)(?:^|[\n\r:_\.)]\s*)SEPARATE\s+JOINT\s+CONCURRING\s+OPINION",
        r"(?i)(?:^|[\n\r:_\.)]\s*)(?:CONCURRING|DISSENTING|PARTLY\s+DISSENTING)\s+OPINION",
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINIONS?\s+S[ÉE]PAR[ÉE]ES?(?:\s+SUIVANTES)?",
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINION\s+COMMUNE\s+EN\s+PARTIE\s+(?:DISSIDENTE|CONCORDANTE)",
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINION\s+(?:CONCORDANTE|DISSIDENTE|PARTIELLEMENT\s+DISSIDENTE)",
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINION\s+PARTIELLEMENT\s+CONCORDANTE(?:\s+ET\s+PARTIELLEMENT\s+DISSIDENTE)?",
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINION\s+PARTIELLEMENT\s+DISSIDENTE(?:\s+ET\s+PARTIELLEMENT\s+CONCORDANTE)?",
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINION\s*,?\s+EN\s+PARTIE\s+(?:DISSIDENTE|CONCORDANTE)",
        r"(?i)(?:^|[\n\r:_\.)]\s*)OPINION\s+S[ÉE]PAR[ÉE]E(?:\s+CONCORDANTE|\s+DISSIDENTE)?",
    ],
    "appendix": [
        r"(?:^|[\n\r:_\.)]\s*)APPENDIX(?=\s*(?:\n|$|[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z])))",
        r"(?:^|[\n\r:_\.)]\s*)ANNEX(?=\s*(?:\n|$|[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z])))",
        r'(?:^|[\n\r:_\.)"]\s*|\s{2,})APPENDIX(?=\s*(?:\n|$|[A-Z]))',
        r'(?:^|[\n\r:_\.)"]\s*|\s{2,})ANNEX(?=\s*(?:\n|$|[A-Z]))',
        r"(?:^|[\n\r:_\.)]\s*)ANNEXE(?=\s*(?:\n|$|[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z])))",
        r'(?:^|[\n\r:_\.)"]\s*|\s{2,})ANNEXE(?=\s*(?:\n|$|[A-Z]))',
    ],
    "subject_matter": [
        r"(?:^|\n)\s*SUBJECT\s+MATTER\s+OF\s+THE\s+CASE\s*(?:\n|$)",
        r"(?<=[\.)\s:])SUBJECT\s+MATTER\s+OF\s+THE\s+CASE(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
    ],
    "court_assessment": [
        r"(?:^|\n)\s*THE\s+COURT['\u2019\u2018]S\s+ASSESSMENT\s*(?:\n|$)",
        r"(?<=[\.)\s:])THE\s+COURT['\u2019\u2018]S\s+ASSESSMENT(?=\s*[:—–-]?\s*(?:\d|[IVX]+\.|[A-Z]))",
    ],
}


def detect_document_type(text: str) -> str:
    """Detect the document family from content patterns."""
    if not text:
        return "unknown"

    for doc_type, patterns in DOCUMENT_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return doc_type

    return "standard"


def normalize_meta_value(value: Any) -> str:
    """Normalize metadata values for stable comparisons."""
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if not text else text.upper()


def _detect_content_routing(text: str) -> Optional[str]:
    """Backward-compatible content routing helper."""
    if not text:
        return None

    for family, patterns in CONTENT_ROUTING_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return family
    return None


def choose_parser_mode(
    text: str,
    metadata_doctype: Optional[str] = None,
    metadata_doctypebranch: Optional[str] = None,
    detected_doc_type: Optional[str] = None,
) -> str:
    """Choose parser mode from metadata + lightweight content detection."""
    doctype = normalize_meta_value(metadata_doctype)
    doctypebranch = normalize_meta_value(metadata_doctypebranch)
    content_doc_type = detected_doc_type or detect_document_type(text)

    if doctype in INFO_NOTE_DOCTYPES or doctypebranch in INFO_NOTE_BRANCHES:
        return "info_note"
    if doctype in PRESS_RELEASE_DOCTYPES:
        return "press_release"
    if doctype in COMMUNICATED_DOCTYPES or doctypebranch in COMMUNICATED_BRANCHES:
        return "communicated_case"
    if doctype in COMMISSION_DECISION_DOCTYPES or doctypebranch in COMMISSION_DECISION_BRANCHES:
        return "commission_decision"

    if not doctype and not doctypebranch:
        if content_doc_type == "information_note":
            return "info_note"
        if content_doc_type == "press_release":
            return "press_release"
        if content_doc_type == "communicated_case":
            return "communicated_case"

    return "standard"


def compile_nonstandard_patterns() -> Dict[str, Dict[str, List[re.Pattern]]]:
    """Compile relaxed patterns used for non-standard document families."""
    compiled: Dict[str, Dict[str, List[re.Pattern]]] = {}
    for parser_mode, section_map in NONSTANDARD_SEGMENTATION_PATTERNS.items():
        compiled[parser_mode] = {}
        for section, patterns in section_map.items():
            compiled[parser_mode][section] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                for pattern in patterns
            ]
    return compiled


def compile_patterns() -> Dict[str, List[re.Pattern]]:
    """Compile all regex patterns for efficient matching."""
    compiled: Dict[str, List[re.Pattern]] = {}
    for section, patterns in SEGMENTATION_PATTERNS.items():
        if section in {"operative", "court_assessment"}:
            compiled[section] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                for pattern in patterns
            ]
        elif section in {"procedure", "facts", "complaints", "law", "appendix", "separate_opinion"}:
            compiled[section] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                for pattern in patterns
            ]
        else:
            compiled[section] = [re.compile(pattern, re.MULTILINE) for pattern in patterns]
    return compiled


_COMPILED_PATTERNS = compile_patterns()
_COMPILED_NONSTANDARD = compile_nonstandard_patterns()


def find_section_boundaries(
    text: str,
    compiled_patterns: Dict[str, List[re.Pattern]],
    original_text: str | None = None,
) -> List[Tuple[str, int, int, str]]:
    """Find all section boundaries in the text."""
    boundaries: List[Tuple[str, int, int, str]] = []
    seen_positions = set()
    base_text = original_text if original_text is not None else text

    uppercase_only_sections = {"procedure", "facts", "law", "complaints", "subject_matter"}
    header_position_sections = {"procedure", "facts", "complaints", "law", "appendix", "separate_opinion"}

    def is_header_like(start_pos: int, end_pos: int) -> bool:
        prefix_start = base_text.rfind("\n", 0, start_pos) + 1
        prefix = base_text[prefix_start:start_pos]
        suffix = base_text[end_pos:end_pos + 20]
        before = base_text[max(0, start_pos - 5):start_pos]
        before_ok = prefix.strip() == "" or re.search(r'[\n\r\.\):;_\-–—"”]\s*$', before)
        if not before_ok and start_pos < len(base_text) and base_text[start_pos] in {".", ":", ")", ";", '"', "”"}:
            before_ok = True
        if not before_ok:
            if re.search(r"_{3,}\s*$", prefix) or re.search(r"\s{5,}$", prefix):
                before_ok = True
        if not before_ok:
            return False
        return bool(
            re.match(
                r"[\s:—–\-]*\d|[\s:—–\-]*\n|[\s:—–\-]*[IVX]+\.|[\s:—–\-]*[A-Z]|[\s:—–\-]*[\(\[]",
                suffix,
            )
        )

    def is_appendix_inline_header(start_pos: int, end_pos: int, matched_text: str) -> bool:
        prefix_start = base_text.rfind("\n", 0, start_pos) + 1
        prefix = base_text[prefix_start:start_pos]
        if not (re.search(r"\s{2,}$", prefix) or re.match(r"^\s{2,}", matched_text)):
            return False
        if re.search(r"[a-z]", matched_text):
            return False
        suffix = base_text[end_pos:end_pos + 20]
        return bool(re.match(r"[A-Z]", suffix))

    def has_initials_prefix(start_pos: int) -> bool:
        prefix = base_text[max(0, start_pos - 60):start_pos]
        if not prefix:
            return False
        cleaned = re.sub(r"[\u2010-\u2015-]", ".", prefix)
        cleaned = cleaned.replace(" ", "")
        cleaned = re.sub(r"\.+", ".", cleaned)
        return re.search(r"(?:[A-Z]\.){2,}[A-Z]?$", cleaned) is not None

    def is_mostly_uppercase(value: str, min_ratio: float = 0.8) -> bool:
        letters = [char for char in value if char.isalpha()]
        if not letters:
            return False
        upper_count = sum(1 for char in letters if char.upper() == char and char.lower() != char)
        return (upper_count / len(letters)) >= min_ratio

    def get_effective_header_span(start_pos: int, matched_text: str) -> Tuple[int, int]:
        if not matched_text:
            return start_pos, start_pos

        first_content = re.search(r'[^\s\.\):;_\-–—"”]', matched_text)
        if first_content is None:
            first_content = re.search(r"\S", matched_text)
        header_start = start_pos + (first_content.start() if first_content else 0)

        stripped_right = matched_text.rstrip()
        header_end = start_pos + len(stripped_right)
        if header_end < header_start:
            header_end = header_start
        return header_start, header_end

    def is_strong_header(section: str, matched_text: str) -> bool:
        mt = matched_text.upper()
        if section == "law":
            return any(k in mt for k in ["THE LAW", "AS TO THE LAW", "EN DROIT", "LE DROIT", "SUR LE DROIT", "RELEVANT LEGAL FRAMEWORK"])
        if section == "facts":
            return any(
                k in mt
                for k in [
                    "THE FACTS",
                    "EN FAIT",
                    "FAITS",
                    "LES FAITS",
                    "CIRCUMSTANCES OF THE CASE",
                    "LES CIRCONSTANCES DE L’AFFAIRE",
                    "LES CIRCONSTANCES DE L'AFFAIRE",
                    "LES CIRCONSTANCES DE L’ESPÈCE",
                    "LES CIRCONSTANCES DE L'ESPÈCE",
                ]
            )
        if section == "procedure":
            return bool(re.search(r"PROCEDURE|PROCEEDING|PROC(?:É|E\u0301|é|e\u0301)DURE", mt))
        if section == "complaints":
            return any(k in mt for k in ["COMPLAINT", "GRIEF", "ALLEGED VIOLATION"])
        if section == "separate_opinion":
            return "OPINION" in mt
        if section == "appendix":
            return any(k in mt for k in ["APPENDIX", "ANNEXE", "ANNEX"])
        if section == "operative":
            return any(k in mt for k in ["FOR THESE REASONS", "PAR CES MOTIFS", "POUR CES MOTIFS"])
        if section == "court_assessment":
            return "COURT" in mt and "ASSESSMENT" in mt
        if section == "subject_matter":
            return "SUBJECT MATTER" in mt
        return False

    strong_sections = set()
    for section, patterns in compiled_patterns.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                header_start, header_end = get_effective_header_span(match.start(), match.group())
                if section in header_position_sections and not is_header_like(header_start, header_end):
                    continue
                if is_strong_header(section, base_text[header_start:header_end]):
                    strong_sections.add(section)
                    break
            if section in strong_sections:
                break

    for section, patterns in compiled_patterns.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                start_pos = match.start()
                header_start, header_end = get_effective_header_span(start_pos, match.group())
                matched_text = base_text[header_start:header_end]

                if section in uppercase_only_sections:
                    if re.search(r"[a-z]", matched_text):
                        prefix_start = base_text.rfind("\n", 0, header_start) + 1
                        prefix = base_text[prefix_start:header_start]
                        if not is_mostly_uppercase(matched_text):
                            if not (re.search(r"_{3,}\s*$", prefix) or re.search(r"\s{5,}$", prefix)):
                                continue
                        elif prefix.strip() != "" and not (re.search(r"_{3,}\s*$", prefix) or re.search(r"\s{5,}$", prefix)):
                            continue

                    mt_upper = matched_text.upper()
                    if section == "law":
                        if not any(kw in mt_upper for kw in ["THE LAW", "EN DROIT", "LE DROIT", "SUR LE DROIT", "RELEVANT LEGAL FRAMEWORK"]):
                            continue
                    elif section == "facts":
                        if not any(
                            kw in mt_upper
                            for kw in [
                                "THE FACTS",
                                "EN FAIT",
                                "FAITS",
                                "LES FAITS",
                                "CIRCUMSTANCES OF THE CASE",
                                "LES CIRCONSTANCES DE L’AFFAIRE",
                                "LES CIRCONSTANCES DE L'AFFAIRE",
                                "LES CIRCONSTANCES DE L’ESPÈCE",
                                "LES CIRCONSTANCES DE L'ESPÈCE",
                            ]
                        ):
                            continue
                    elif section == "procedure":
                        if not re.search(r"PROCEDURE|PROCEEDING|PROC(?:É|E\u0301|é|e\u0301)DURE", mt_upper):
                            continue
                    elif section == "complaints":
                        if not any(kw in mt_upper for kw in ["COMPLAINT", "GRIEF", "ALLEGED VIOLATION"]):
                            continue
                        following_text = text[header_start:header_start + 160]
                        lookback = text[max(0, header_start - 350):header_start]
                        if re.search(
                            r"(?:THE\s+COMPLAINTS?|LES?\s+GRIEFS?|ALLEGED\s+VIOLATION|VIOLATIONS?\s+ALL[ÉE]GU[ÉE]E)",
                            matched_text,
                        ):
                            if re.search(
                                r"EN\s+DROIT|AS\s+TO\s+THE\s+LAW|THE\s+LAW|THE\s+COURT['\u2019\u2018]S\s+ASSESSMENT",
                                lookback,
                            ):
                                continue
                        if re.search(r"ALLEGED\s+VIOLATION\S*\s+OF\s+ARTICLE", following_text):
                            continue
                        if re.search(r"ALLEGED\s+VIOLATION|VIOLATION\S*\s+ALL[ÉE]GU[ÉE]E", matched_text):
                            if re.search(
                                r"EN\s+DROIT|AS\s+TO\s+THE\s+LAW|THE\s+LAW|THE\s+COURT['\u2019\u2018]S\s+ASSESSMENT",
                                lookback,
                            ):
                                continue
                        if not is_header_like(header_start, header_end):
                            continue
                    elif section == "subject_matter":
                        if "SUBJECT MATTER" not in mt_upper:
                            continue

                if section == "court_assessment":
                    if not re.search(r"COURT['\u2019\u2018]S\s+ASSESSMENT", matched_text, re.IGNORECASE):
                        continue
                    if re.search(r"[a-z]", matched_text):
                        if not re.fullmatch(r"The\s+Court['\u2019\u2018]s\s+Assessment", matched_text):
                            continue
                    index = header_start - 1
                    while index >= 0 and text[index].isspace():
                        index -= 1
                    if index >= 0 and text[index] not in {"\n", "\r", ".", ":", ")"}:
                        continue

                if section in header_position_sections:
                    if not is_header_like(header_start, header_end):
                        if section == "separate_opinion" and has_initials_prefix(header_start):
                            pass
                        elif section == "appendix" and is_appendix_inline_header(header_start, header_end, matched_text):
                            pass
                        else:
                            continue

                if section in strong_sections and not is_strong_header(section, matched_text):
                    if section == "law" and re.search(r"RELEVANT\s+LEGAL\s+FRAMEWORK", matched_text, re.IGNORECASE):
                        pass
                    else:
                        continue

                if header_start not in seen_positions:
                    boundaries.append((section, header_start, header_end, matched_text))
                    seen_positions.add(header_start)

    boundaries.sort(key=lambda x: x[1])

    filtered: List[Tuple[str, int, int, str]] = []
    last_pos = -1000
    last_section = None
    for boundary in boundaries:
        section, pos, _, matched_text = boundary
        if pos - last_pos >= 100:
            filtered.append(boundary)
            last_pos = pos
            last_section = section
        elif section != last_section and is_strong_header(section, matched_text):
            filtered.append(boundary)
            last_pos = pos
            last_section = section

    return filtered


def extract_segments_from_boundaries(
    text: str,
    boundaries: List[Tuple[str, int, int, str]],
    min_segment_length: int = 50,
) -> Dict[str, str]:
    """Build section dictionary from ordered boundary tuples."""
    if not boundaries:
        return {}

    segments: Dict[str, str] = {}
    for index, (section, start, end, matched_text) in enumerate(boundaries):
        if index + 1 < len(boundaries):
            next_start = boundaries[index + 1][1]
            section_text = text[start:next_start].strip()
        else:
            section_text = text[start:].strip()

        section_min_length = min_segment_length
        if section == "subject_matter":
            section_min_length = min(section_min_length, 20)

        if len(section_text) < section_min_length:
            continue

        if section in segments:
            segments[section] += "\n\n" + section_text
        else:
            segments[section] = section_text

    return segments


def segment_text(
    text: str,
    compiled_patterns: Dict[str, List[re.Pattern]],
    min_segment_length: int = 50,
) -> Dict[str, str]:
    """Segment text into sections using the primary pattern set."""
    if not text or not isinstance(text, str):
        return {}

    normalized_text = text.replace("_", " ")
    boundaries = find_section_boundaries(normalized_text, compiled_patterns, original_text=text)
    return extract_segments_from_boundaries(text, boundaries, min_segment_length=min_segment_length)


def segment_nonstandard_text(
    text: str,
    fallback_patterns: Dict[str, List[re.Pattern]],
    min_segment_length: int = 35,
) -> Dict[str, str]:
    """Segment non-standard formats with relaxed family-specific rules."""
    if not text or not isinstance(text, str):
        return {}

    normalized_text = text.replace("_", " ")
    boundaries = find_section_boundaries(normalized_text, fallback_patterns, original_text=text)
    return extract_segments_from_boundaries(text, boundaries, min_segment_length=min_segment_length)


def _segment_text_nonstandard(
    text: str,
    compiled_ns_patterns: Dict[str, List[re.Pattern]],
    min_segment_length: int = 35,
) -> Dict[str, str]:
    """Backward-compatible alias for the relaxed segmenter."""
    return segment_nonstandard_text(text, compiled_ns_patterns, min_segment_length=min_segment_length)


def segment_echr_texts(
    df: pd.DataFrame,
    allowed_langs: Tuple[str, ...] = ("ENG", "FRE"),
    min_segment_length: int = 50,
    max_text_length: int = 5_000_000,
) -> pd.DataFrame:
    """Segment ECHR full texts into structured legal sections."""
    required_cols = {"itemid", "languageisocode", "fulltext"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. Available columns: {list(df.columns)}"
        )

    output_cols = ["itemid", "languageisocode", "ecli", "parser_mode"] + SECTION_NAMES + ["num_sections", "error"]
    if df.empty:
        return pd.DataFrame(columns=output_cols)

    allowed = {lang.upper() for lang in allowed_langs}
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
            if lang not in allowed:
                result["parser_mode"] = "skipped_language"
                for section in SECTION_NAMES:
                    result[section] = None
                result["num_sections"] = 0
                result["error"] = None
                results.append(result)
                continue

            fulltext = row.fulltext
            if not fulltext or not isinstance(fulltext, str):
                result["parser_mode"] = "standard"
                for section in SECTION_NAMES:
                    result[section] = None
                result["num_sections"] = 0
                result["error"] = "Missing or empty fulltext"
                results.append(result)
                continue

            if len(fulltext) > max_text_length:
                result["parser_mode"] = "standard"
                for section in SECTION_NAMES:
                    result[section] = None
                result["num_sections"] = 0
                result["error"] = f"Text too long ({len(fulltext)} chars)"
                logger.warning("Skipping %s: text too long (%d chars)", row.itemid, len(fulltext))
                results.append(result)
                continue

            detected_doc_type = detect_document_type(fulltext)
            parser_mode = choose_parser_mode(
                fulltext,
                metadata_doctype=getattr(row, "doctype", None) if has_doctype else None,
                metadata_doctypebranch=getattr(row, "doctypebranch", None) if has_doctypebranch else None,
                detected_doc_type=detected_doc_type,
            )
            result["parser_mode"] = parser_mode

            if parser_mode == "standard":
                segments = segment_text(fulltext, _COMPILED_PATTERNS, min_segment_length=min_segment_length)
            elif parser_mode in {"communicated_case", "commission_decision"}:
                segments = segment_text(fulltext, _COMPILED_PATTERNS, min_segment_length=min_segment_length)
                if not segments:
                    relaxed = _COMPILED_NONSTANDARD.get(parser_mode, {})
                    segments = segment_nonstandard_text(fulltext, relaxed, min_segment_length=35)
            else:
                segments = {}

            for section in SECTION_NAMES:
                result[section] = segments.get(section)
            result["num_sections"] = sum(1 for section in SECTION_NAMES if result[section] is not None)

            should_soft_skip = parser_mode in SOFT_SKIP_PARSER_MODES and result["num_sections"] == 0
            if segments or should_soft_skip:
                result["error"] = None
            else:
                result["error"] = "No sections found in text"

        except Exception as exc:
            logger.error("Segmentation failed for %s: %s", result.get("itemid", "unknown"), exc)
            result["parser_mode"] = result.get("parser_mode", "standard")
            for section in SECTION_NAMES:
                result[section] = None
            result["num_sections"] = 0
            result["error"] = str(exc)

        results.append(result)

    return pd.DataFrame(results, columns=output_cols)
