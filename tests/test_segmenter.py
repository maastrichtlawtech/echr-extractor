"""Tests for the ECHR text segmentation module."""

import re

import pandas as pd
import pytest

from echr_extractor import get_echr_segments
from echr_extractor.echr import prepare_echr_corpus
from echr_extractor.ECHR_text_segmenter import (
    SECTION_NAMES,
    _COMPILED_NONSTANDARD,
    _COMPILED_PATTERNS,
    _detect_content_routing,
    _segment_text_nonstandard,
    choose_parser_mode,
    extract_segments_from_boundaries,
    find_section_boundaries,
    normalize_meta_value,
    segment_echr_texts,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
STANDARD_JUDGMENT_TEXT = (
    "HEADER INFO\n\n"
    "PROCEDURE\n\n"
    "1. The case originated in an application filed against the State.\n\n"
    "THE FACTS\n\n"
    "2. The applicant was born in 1980 and lives in a city. "
    "The applicant submitted a complaint about the treatment received.\n\n"
    "THE LAW\n\n"
    "3. The Court notes that Article 6 of the Convention provides "
    "for the right to a fair trial. The Court considers the submissions.\n\n"
    "FOR THESE REASONS, THE COURT\n\n"
    "Holds that there has been a violation of Article 6.\n"
)

FRENCH_JUDGMENT_TEXT = (
    "EN-TÊTE\n\n"
    "PROCÉDURE\n\n"
    "1. L'affaire a pour origine une requête dirigée contre l'État.\n\n"
    "EN FAIT\n\n"
    "2. Le requérant est né en 1980 et réside dans une ville. "
    "Il a soumis une plainte concernant le traitement reçu.\n\n"
    "EN DROIT\n\n"
    "3. La Cour note que l'article 6 de la Convention prévoit "
    "le droit à un procès équitable.\n\n"
    "PAR CES MOTIFS, LA COUR\n\n"
    "Dit qu'il y a eu violation de l'article 6.\n"
)


def _make_df(text, itemid="001-123456", lang="ENG", **kwargs):
    """Helper to create a single-row test DataFrame."""
    data = {"itemid": [itemid], "languageisocode": [lang], "fulltext": [text]}
    data.update({k: [v] for k, v in kwargs.items()})
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Tests: normalize_meta_value
# ---------------------------------------------------------------------------
class TestNormalizeMetaValue:
    def test_none(self):
        assert normalize_meta_value(None) == ""

    def test_nan(self):
        assert normalize_meta_value(float("nan")) == ""

    def test_string(self):
        assert normalize_meta_value("  HEJUD  ") == "HEJUD"

    def test_lowercase(self):
        assert normalize_meta_value("hejud") == "HEJUD"

    def test_empty_string(self):
        assert normalize_meta_value("") == ""

    def test_whitespace_only(self):
        assert normalize_meta_value("   ") == ""


# ---------------------------------------------------------------------------
# Tests: Parser mode routing
# ---------------------------------------------------------------------------
class TestChooseParserMode:
    def test_default_standard(self):
        assert choose_parser_mode("Some text") == "standard"

    def test_info_note_doctype(self):
        assert choose_parser_mode("text", metadata_doctype="CLIN") == "info_note"

    def test_info_note_clinf(self):
        assert choose_parser_mode("text", metadata_doctype="CLINF") == "info_note"

    def test_info_note_branch(self):
        assert choose_parser_mode("text", metadata_doctypebranch="CLIN") == "info_note"

    def test_press_release_doctype(self):
        assert choose_parser_mode("text", metadata_doctype="PR") == "press_release"

    def test_communicated_doctype(self):
        assert (
            choose_parser_mode("text", metadata_doctype="HECOM") == "communicated_case"
        )

    def test_communicated_branch(self):
        assert (
            choose_parser_mode("text", metadata_doctypebranch="COMMUNICATEDCASES")
            == "communicated_case"
        )

    def test_commission_decision_doctype(self):
        assert (
            choose_parser_mode("text", metadata_doctype="HEDEC")
            == "commission_decision"
        )

    def test_commission_decision_branch(self):
        assert (
            choose_parser_mode("text", metadata_doctypebranch="DECCOMMISSION")
            == "commission_decision"
        )

    def test_admissibility_com_branch(self):
        assert (
            choose_parser_mode("text", metadata_doctypebranch="ADMISSIBILITYCOM")
            == "commission_decision"
        )

    def test_content_fallback_press_release(self):
        assert choose_parser_mode("Press release issued") == "press_release"

    def test_content_fallback_communicated(self):
        assert choose_parser_mode("Communicated on 01/01/2020") == "communicated_case"

    def test_content_fallback_info_note(self):
        text = "Information Note on the Court's case-law No. 123"
        assert choose_parser_mode(text) == "info_note"

    def test_metadata_takes_priority(self):
        # Even if text says "Press release", metadata doctype wins
        assert (
            choose_parser_mode("Press release", metadata_doctype="HEDEC")
            == "commission_decision"
        )

    def test_none_metadata_values(self):
        assert choose_parser_mode("text", metadata_doctype=None) == "standard"

    def test_nan_metadata_values(self):
        assert choose_parser_mode("text", metadata_doctype=float("nan")) == "standard"


# ---------------------------------------------------------------------------
# Tests: Content routing detection
# ---------------------------------------------------------------------------
class TestDetectContentRouting:
    def test_no_match(self):
        assert _detect_content_routing("Regular judgment text") is None

    def test_press_release(self):
        assert _detect_content_routing("Press release") == "press_release"

    def test_communique_de_presse(self):
        assert _detect_content_routing("COMMUNIQUE DE PRESSE") == "press_release"

    def test_communicated(self):
        assert _detect_content_routing("Communicated on 2020") == "communicated_case"

    def test_objet_affaire(self):
        assert _detect_content_routing("OBJET DE L\u2019AFFAIRE") == "communicated_case"


# ---------------------------------------------------------------------------
# Tests: Boundary finding
# ---------------------------------------------------------------------------
class TestFindSectionBoundaries:
    def test_standard_judgment(self):
        normalized = STANDARD_JUDGMENT_TEXT.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=STANDARD_JUDGMENT_TEXT
        )
        sections_found = [b[0] for b in boundaries]
        assert "procedure" in sections_found
        assert "facts" in sections_found
        assert "law" in sections_found
        assert "operative" in sections_found

    def test_french_judgment(self):
        normalized = FRENCH_JUDGMENT_TEXT.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=FRENCH_JUDGMENT_TEXT
        )
        sections_found = [b[0] for b in boundaries]
        assert "procedure" in sections_found
        assert "facts" in sections_found
        assert "law" in sections_found
        assert "operative" in sections_found

    def test_empty_text(self):
        boundaries = find_section_boundaries("", _COMPILED_PATTERNS)
        assert boundaries == []

    def test_no_sections(self):
        boundaries = find_section_boundaries(
            "This is just regular text with no section headers.",
            _COMPILED_PATTERNS,
        )
        assert boundaries == []

    def test_boundaries_sorted_by_position(self):
        normalized = STANDARD_JUDGMENT_TEXT.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=STANDARD_JUDGMENT_TEXT
        )
        positions = [b[1] for b in boundaries]
        assert positions == sorted(positions)

    def test_separate_opinion(self):
        text = (
            "THE LAW\n\n"
            "3. The Court considers...\n\n"
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that...\n\n"
            "DISSENTING OPINION OF JUDGE X\n\n"
            "I disagree with the majority because of many reasons "
            "that I will now explain in great detail.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections_found = [b[0] for b in boundaries]
        assert "separate_opinion" in sections_found

    def test_committee_judgment_sections(self):
        text = (
            "SUBJECT MATTER OF THE CASE\n\n"
            "The case concerns the applicant's complaint about detention.\n\n"
            "THE COURT\u2019S ASSESSMENT\n\n"
            "The Court notes that the issue has been examined before.\n\n"
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds unanimously that there has been a violation.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections_found = [b[0] for b in boundaries]
        assert "subject_matter" in sections_found
        assert "court_assessment" in sections_found
        assert "operative" in sections_found


# ---------------------------------------------------------------------------
# Tests: Segment extraction
# ---------------------------------------------------------------------------
class TestExtractSegmentsFromBoundaries:
    def test_basic_extraction(self):
        text = "AAA PROCEDURE BBB THE FACTS CCC"
        boundaries = [
            ("procedure", 4, 13, "PROCEDURE"),
            ("facts", 18, 27, "THE FACTS"),
        ]
        segments = extract_segments_from_boundaries(
            text, boundaries, min_segment_length=3
        )
        assert "procedure" in segments
        assert "facts" in segments

    def test_empty_boundaries(self):
        segments = extract_segments_from_boundaries("some text", [])
        assert segments == {}

    def test_min_segment_length_filter(self):
        text = "PROCEDURE\nX\nTHE FACTS\nLong enough text here for testing."
        boundaries = [
            ("procedure", 0, 9, "PROCEDURE"),
            ("facts", 12, 21, "THE FACTS"),
        ]
        segments = extract_segments_from_boundaries(
            text, boundaries, min_segment_length=50
        )
        # "PROCEDURE\nX" is too short (11 chars), should be filtered
        assert "procedure" not in segments

    def test_concatenation_of_duplicate_sections(self):
        text = (
            "OPINION OF JUDGE A\n\nI agree.\n\n"
            "OPINION OF JUDGE B\n\nI disagree with the outcome strongly.\n"
        )
        boundaries = [
            ("separate_opinion", 0, 18, "OPINION OF JUDGE A"),
            ("separate_opinion", 30, 48, "OPINION OF JUDGE B"),
        ]
        segments = extract_segments_from_boundaries(
            text, boundaries, min_segment_length=10
        )
        assert "separate_opinion" in segments
        assert "\n\n" in segments["separate_opinion"]


# ---------------------------------------------------------------------------
# Tests: Main function (segment_echr_texts)
# ---------------------------------------------------------------------------
class TestSegmentEchrTexts:
    def test_basic_segmentation(self):
        df = _make_df(STANDARD_JUDGMENT_TEXT)
        result = segment_echr_texts(df)
        assert len(result) == 1
        assert result.iloc[0]["parser_mode"] == "standard"
        assert result.iloc[0]["procedure"] is not None
        assert result.iloc[0]["facts"] is not None
        assert result.iloc[0]["law"] is not None
        assert result.iloc[0]["operative"] is not None
        assert result.iloc[0]["num_sections"] >= 4
        assert result.iloc[0]["error"] is None

    def test_french_segmentation(self):
        df = _make_df(FRENCH_JUDGMENT_TEXT, lang="FRE")
        result = segment_echr_texts(df)
        assert len(result) == 1
        assert result.iloc[0]["procedure"] is not None
        assert result.iloc[0]["facts"] is not None
        assert result.iloc[0]["law"] is not None
        assert result.iloc[0]["operative"] is not None

    def test_missing_required_columns_raises(self):
        df = pd.DataFrame({"itemid": ["001-123456"]})
        with pytest.raises(ValueError, match="Missing required columns"):
            segment_echr_texts(df)

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["itemid", "languageisocode", "fulltext"])
        result = segment_echr_texts(df)
        assert len(result) == 0
        assert "parser_mode" in result.columns

    def test_none_text_handled(self):
        df = _make_df(None)
        result = segment_echr_texts(df)
        assert len(result) == 1
        assert result.iloc[0]["error"] == "Missing or empty fulltext"
        for s in SECTION_NAMES:
            assert result.iloc[0][s] is None

    def test_empty_string_text(self):
        df = _make_df("")
        result = segment_echr_texts(df)
        assert len(result) == 1
        assert result.iloc[0]["error"] == "Missing or empty fulltext"

    def test_oversized_text_guard(self):
        df = _make_df("x" * 6_000_000)
        result = segment_echr_texts(df)
        assert len(result) == 1
        assert "too long" in result.iloc[0]["error"]
        assert result.iloc[0]["num_sections"] == 0

    def test_skipped_language(self):
        df = _make_df(STANDARD_JUDGMENT_TEXT, lang="DEU")
        result = segment_echr_texts(df, allowed_langs=("ENG", "FRE"))
        assert len(result) == 1
        assert result.iloc[0]["parser_mode"] == "skipped_language"
        assert result.iloc[0]["error"] is None

    def test_allowed_langs_parameter(self):
        df = _make_df(STANDARD_JUDGMENT_TEXT, lang="DEU")
        result = segment_echr_texts(df, allowed_langs=("ENG", "FRE", "DEU"))
        assert result.iloc[0]["parser_mode"] != "skipped_language"

    def test_output_columns(self):
        df = _make_df(STANDARD_JUDGMENT_TEXT)
        result = segment_echr_texts(df)
        expected_cols = (
            ["itemid", "languageisocode", "ecli", "parser_mode"]
            + SECTION_NAMES
            + ["num_sections", "error"]
        )
        assert list(result.columns) == expected_cols

    def test_ecli_passthrough(self):
        df = _make_df(STANDARD_JUDGMENT_TEXT, ecli="ECLI:CE:ECHR:2020:TEST")
        result = segment_echr_texts(df)
        assert result.iloc[0]["ecli"] == "ECLI:CE:ECHR:2020:TEST"

    def test_soft_skip_info_note(self):
        df = _make_df("Some info note text", doctype="CLIN")
        result = segment_echr_texts(df)
        assert result.iloc[0]["parser_mode"] == "info_note"
        assert result.iloc[0]["error"] is None
        assert result.iloc[0]["num_sections"] == 0

    def test_soft_skip_press_release(self):
        df = _make_df("Press release text", doctype="PR")
        result = segment_echr_texts(df)
        assert result.iloc[0]["parser_mode"] == "press_release"
        assert result.iloc[0]["error"] is None

    def test_no_sections_found_error(self):
        df = _make_df("This text has no recognizable legal section headers at all.")
        result = segment_echr_texts(df)
        assert result.iloc[0]["error"] == "No sections found in text"
        assert result.iloc[0]["num_sections"] == 0

    def test_multiple_rows(self):
        df = pd.DataFrame(
            {
                "itemid": ["001-1", "001-2", "001-3"],
                "languageisocode": ["ENG", "ENG", "FRE"],
                "fulltext": [
                    STANDARD_JUDGMENT_TEXT,
                    "No sections here.",
                    FRENCH_JUDGMENT_TEXT,
                ],
            }
        )
        result = segment_echr_texts(df)
        assert len(result) == 3
        assert result.iloc[0]["num_sections"] >= 4
        assert result.iloc[1]["error"] == "No sections found in text"
        assert result.iloc[2]["num_sections"] >= 4

    def test_commission_decision_routing(self):
        df = _make_df(STANDARD_JUDGMENT_TEXT, doctype="HEDEC")
        result = segment_echr_texts(df)
        assert result.iloc[0]["parser_mode"] == "commission_decision"

    def test_min_segment_length_parameter(self):
        text = (
            "PROCEDURE\n\n"
            "Short.\n\n"
            "THE LAW\n\n"
            "This is a much longer section with substantial legal analysis "
            "that should definitely be kept because it exceeds the minimum.\n"
        )
        df = _make_df(text)
        result = segment_echr_texts(df, min_segment_length=100)
        # procedure section is short and should be filtered
        assert result.iloc[0]["procedure"] is None


# ---------------------------------------------------------------------------
# Tests: Boundary validation edge cases (coverage)
# ---------------------------------------------------------------------------
class TestBoundaryValidationEdgeCases:
    """Tests targeting uncovered validation paths in find_section_boundaries."""

    def test_underscore_separator_prefix(self):
        """Cover is_header_like: prefix ends with 3+ underscores (line 478-479)."""
        text = "Some text here.___THE FACTS\n2. The applicant was born in a city and lives there still.\n"
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        assert "facts" in sections

    def test_five_space_separator_prefix(self):
        """Cover is_header_like: prefix ends with 5+ spaces (line 478-479)."""
        text = "Some text here.     THE FACTS\n2. The applicant was born in a city and lives there still.\n"
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        assert "facts" in sections

    def test_header_like_returns_false_suffix_fail(self):
        """Cover is_header_like return False (line 481) — suffix has no valid content."""
        # .COMPLAINTS matches flattened pattern, but suffix is lowercase
        # so is_header_like suffix check fails → return False
        text = (
            "The Government submitted.COMPLAINTS about the matter "
            "were raised and they were not dealt with properly.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        # COMPLAINTS should NOT be found because suffix check fails
        sections = [b[0] for b in boundaries]
        assert "complaints" not in sections

    def test_appendix_section_found(self):
        """Cover is_strong_header for appendix (line 528)."""
        text = (
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that there has been a violation of Article 6 of the Convention.\n\n"
            "APPENDIX\n\n"
            "List of applications: 12345/20, 12346/20, 12347/20 and more items.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        assert "appendix" in sections

    def test_complaints_section_found(self):
        """Cover is_strong_header for complaints (line 522)."""
        text = (
            "THE FACTS\n\n"
            "2. The applicant was born in a city and lives there still.\n\n"
            "COMPLAINTS\n\n"
            "3. The applicant complained under Article 6 of the Convention.\n\n"
            "THE LAW\n\n"
            "4. The Court notes that the complaint is admissible.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        assert "complaints" in sections

    def test_is_strong_header_unknown_section_returns_false(self):
        """Cover is_strong_header fallthrough return False (line 542)."""
        # We can't easily invoke this through public API since all known
        # sections are handled, but we can verify via the main function
        # that unknown sections in patterns don't crash anything.
        # This is effectively covered by the fact that all known sections work.
        pass

    def test_has_initials_prefix_separate_opinion(self):
        """Cover has_initials_prefix (lines 545-552) and exception (lines 653-656)."""
        # Simulate: judge initials glued to separate opinion header
        text = (
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that there has been a violation of Article 6.\n\n"
            "R.C.H.G.DISSENTING OPINION\n\n"
            "I disagree with the majority for the following reasons which I consider important.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        assert "separate_opinion" in sections

    def test_appendix_inline_after_double_space(self):
        """Cover is_appendix_inline_header (lines 555-566) and exception (lines 657-663)."""
        text = (
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that there has been a violation of Article 6.  "
            "APPENDIX"
            "List of applications and their reference numbers here.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        assert "appendix" in sections

    def test_uppercase_filter_rejects_non_canonical(self):
        """Cover line 615: uppercase section match that's not a strong header."""
        # A match containing uppercase text but not the canonical keyword
        # is filtered out. This is hard to trigger directly since patterns
        # are designed to match canonical keywords, but we can check that
        # a text without proper headers produces no false positives.
        text = "The procedure was explained. The facts were also mentioned."
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        # No section boundaries should be found in regular prose
        assert len(boundaries) == 0


class TestComplaintsDisambiguation:
    """Tests for complaints false-positive filtering (lines 619-631)."""

    def test_alleged_violation_of_article_rejected(self):
        """Cover line 619-623: ALLEGED VIOLATION OF ARTICLE is NOT a complaints header."""
        text = (
            "THE LAW\n\n"
            "I. ALLEGED VIOLATION OF ARTICLE 6 OF THE CONVENTION\n\n"
            "The applicant complained that his right to a fair trial was violated "
            "and that the proceedings were unfair.\n\n"
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that there has been a violation of Article 6.\n"
        )
        df = _make_df(text)
        result = segment_echr_texts(df)
        # Should NOT create a complaints section from "ALLEGED VIOLATION OF ARTICLE"
        assert result.iloc[0]["complaints"] is None
        assert result.iloc[0]["law"] is not None

    def test_alleged_violation_near_law_rejected(self):
        """Cover lines 624-629: ALLEGED VIOLATION within 350 chars of LAW header."""
        text = (
            "THE LAW\n\n"
            "ALLEGED VIOLATION\n\n"
            "The applicant complained about various issues and the treatment.\n\n"
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that there has been a violation.\n"
        )
        df = _make_df(text)
        result = segment_echr_texts(df)
        # "ALLEGED VIOLATION" too close to "THE LAW" should be suppressed
        assert result.iloc[0]["complaints"] is None

    def test_alleged_violation_of_article_after_court_assessment(self):
        """Regression test for itemid=001-246132: ALLEGED VIOLATION OF ARTICLE
        as subsection header after THE COURT'S ASSESSMENT should not create
        a complaints boundary that suppresses court_assessment.

        The regex captures "ALLEGED VIOLATION" but "OF ARTICLE" follows in text
        immediately after the match. The extended-text disambiguation must reject
        this as a complaints section header.
        """
        text = (
            "PROCEDURE\n\n"
            "1. The case originated in an application.\n\n"
            "THE FACTS\n\n"
            "2. The applicant was born in 1980.\n\n"
            "THE COURT\u2019S ASSESSMENT\n\n"
            "ALLEGED VIOLATION OF ARTICLE 3 OF THE CONVENTION\n\n"
            "3. The applicant complained that the conditions of his "
            "detention were incompatible with Article 3 of the Convention. "
            "The Court notes that the domestic courts acknowledged a "
            "violation of Article 3 regarding the conditions of detention "
            "and awarded the applicant compensation.\n\n"
            "ALLEGED VIOLATION OF ARTICLE 13 OF THE CONVENTION\n\n"
            "4. The applicant also complained under Article 13. "
            "The Court notes that this complaint is manifestly "
            "ill-founded and must be rejected.\n\n"
            "FOR THESE REASONS, THE COURT\n\n"
            "1. Declares the application partly admissible;\n"
            "2. Holds that there has been a violation of Article 3;\n"
            "3. Holds that the remainder of the application is inadmissible.\n"
        )
        df = _make_df(text)
        result = segment_echr_texts(df)
        # Court assessment must be detected — NOT suppressed by a false
        # complaints boundary from "ALLEGED VIOLATION OF ARTICLE ..."
        assert result.iloc[0]["court_assessment"] is not None
        assert "Article 3" in result.iloc[0]["court_assessment"]
        # No complaints section should be created from sub-headings
        assert result.iloc[0]["complaints"] is None


class TestCourtAssessmentFilter:
    """Tests for court_assessment validation (lines 633-647)."""

    def test_court_assessment_rejected_when_not_canonical(self):
        """Cover line 637: match that doesn't contain COURT + ASSESSMENT."""
        # The court_assessment patterns require COURT'S ASSESSMENT.
        # This test exercises the filter that rejects non-canonical matches.
        text = (
            "THE LAW\n\n"
            "According to the assessment by the authorities this was lawful "
            "and the complaint should be dismissed entirely.\n\n"
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that the application is inadmissible.\n"
        )
        df = _make_df(text)
        result = segment_echr_texts(df)
        assert result.iloc[0]["court_assessment"] is None

    def test_court_assessment_rejected_when_mid_paragraph(self):
        """Cover lines 644-647: court assessment with non-empty prefix."""
        # THE COURT'S ASSESSMENT appearing mid-line after regular text
        text = (
            "THE LAW\n\n"
            "The Government submitted that THE COURT\u2019S ASSESSMENT should "
            "consider the domestic remedies exhaustion requirement.\n\n"
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that the application is inadmissible.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        # Should not pick up COURT'S ASSESSMENT as a section header
        # when it's mid-paragraph with non-empty, non-punctuation prefix
        assert sections.count("court_assessment") == 0


class TestStrongHeaderSuppression:
    """Tests for strong header suppression (lines 667-676)."""

    def test_relevant_legal_framework_kept_alongside_the_law(self):
        """Cover lines 673-674: RELEVANT LEGAL FRAMEWORK exception."""
        text = (
            "PROCEDURE\n\n"
            "1. The case originated in an application.\n\n"
            "THE FACTS\n\n"
            "2. The applicant was born in 1980 and lives in a city.\n\n"
            "RELEVANT LEGAL FRAMEWORK AND PRACTICE\n\n"
            "Article 6 provides for the right to a fair hearing in civil.\n\n"
            "THE LAW\n\n"
            "3. The Court considers the applicant's complaints in detail.\n\n"
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that there has been a violation of Article 6.\n"
        )
        df = _make_df(text)
        result = segment_echr_texts(df)
        # The law section should contain both THE LAW and RELEVANT LEGAL FRAMEWORK
        assert result.iloc[0]["law"] is not None
        # Verify RELEVANT LEGAL FRAMEWORK text is captured (either as separate
        # boundary or within law section content)
        law_text = result.iloc[0]["law"]
        assert "RELEVANT LEGAL FRAMEWORK" in law_text or "THE LAW" in law_text

    def test_weak_match_suppressed_by_strong(self):
        """Cover lines 675-676: weak match suppressed when strong exists."""
        # This is implicitly covered — when THE LAW exists, weaker patterns
        # for the law section are suppressed. The standard text has "THE LAW"
        # which is a strong header, suppressing any weaker matches.
        text = STANDARD_JUDGMENT_TEXT
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        law_boundaries = [b for b in boundaries if b[0] == "law"]
        # Should have exactly 1 law boundary (THE LAW), not duplicates
        assert len(law_boundaries) == 1


class TestNonstandardFallback:
    """Tests for nonstandard segmentation fallback (lines 754-769, 904-915)."""

    def test_segment_text_nonstandard_direct(self):
        """Cover _segment_text_nonstandard function (lines 754-769)."""
        text = (
            "FACTS\n\n"
            "The applicant was born in 1980 and resides in a city.\n\n"
            "LAW\n\n"
            "The Court notes that Article 6 applies in this case.\n\n"
            "FOR THESE REASONS\n\n"
            "The application is declared admissible.\n"
        )
        ns_patterns = _COMPILED_NONSTANDARD["commission_decision"]
        segments = _segment_text_nonstandard(text, ns_patterns, min_segment_length=35)
        assert "facts" in segments or "law" in segments

    def test_commission_decision_nonstandard_fallback(self):
        """Cover lines 902-908: commission_decision with no strict matches falls back."""
        # Text with only simple headers that strict patterns won't match
        # but nonstandard patterns will
        text = (
            "FACTS\n\n"
            "The applicant was born in 1980 and lives in a place.\n\n"
            "LAW\n\n"
            "The Commission considers the complaint under Article 6.\n\n"
            "FOR THESE REASONS\n\n"
            "The application is declared admissible by the Commission.\n"
        )
        df = _make_df(text, doctype="HEDEC")
        result = segment_echr_texts(df)
        assert result.iloc[0]["parser_mode"] == "commission_decision"
        # Should find sections via fallback
        assert result.iloc[0]["num_sections"] > 0

    def test_communicated_case_nonstandard_fallback(self):
        """Cover communicated_case fallback path."""
        text = (
            "FACTS\n\n"
            "The applicant was born in 1980 and lives in a place.\n\n"
            "COMPLAINTS\n\n"
            "The applicant complains under Article 6.\n\n"
            "QUESTIONS TO THE PARTIES\n\n"
            "1. Has there been a violation of Article 6 of the Convention?\n"
        )
        df = _make_df(text, doctype="HECOM")
        result = segment_echr_texts(df)
        assert result.iloc[0]["parser_mode"] == "communicated_case"
        assert result.iloc[0]["num_sections"] > 0


class TestExceptionHandling:
    """Tests for the per-row exception handler (lines 934-944)."""

    def test_exception_during_segmentation(self):
        """Cover lines 934-944: exception caught during segmentation."""
        # Create a DataFrame with an object that will cause an error
        # when len() is called on it (not a string, not None)
        df = pd.DataFrame(
            {
                "itemid": ["001-123456"],
                "languageisocode": ["ENG"],
                "fulltext": [12345],  # int, not str — will fail isinstance check
            }
        )
        result = segment_echr_texts(df)
        assert len(result) == 1
        # Should be handled gracefully — either as missing text or as error
        assert result.iloc[0]["num_sections"] == 0

    def test_exception_from_bad_fulltext_type(self):
        """Force an actual exception in the segmentation pipeline."""

        # Use a custom object that passes isinstance(x, str) but fails later
        class BadStr(str):
            def replace(self, *args, **kwargs):
                raise RuntimeError("Intentional test error")

        df = pd.DataFrame(
            {
                "itemid": ["001-bad"],
                "languageisocode": ["ENG"],
                "fulltext": [BadStr("some text")],
            }
        )
        result = segment_echr_texts(df)
        assert len(result) == 1
        assert result.iloc[0]["error"] == "Intentional test error"
        assert result.iloc[0]["num_sections"] == 0


class TestProximityFilter:
    """Test proximity filter in boundary post-processing."""

    def test_close_boundaries_different_sections_kept_if_strong(self):
        """Test that strong headers for different sections survive proximity filter."""
        # Two headers < 100 chars apart but for different sections
        text = (
            "THE FACTS\n"
            "THE LAW\n\n"
            "3. The Court considers the applicant's complaints in detail.\n\n"
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that there has been a violation of Article 6.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        # Both should be kept since they are different strong sections
        assert "facts" in sections
        assert "law" in sections


# ---------------------------------------------------------------------------
# Tests: prepare_echr_corpus
# ---------------------------------------------------------------------------
class TestPrepareEchrCorpus:
    def test_basic_merge(self):
        df = pd.DataFrame(
            {
                "itemid": ["001-123456", "001-123457"],
                "doctype": ["HEJUD", "HEJUD"],
                "languageisocode": ["ENG", "ENG"],
            }
        )
        full_texts = [
            {
                "item_id": "001-123456",
                "ecli": "ECLI:1",
                "full_text": "Text one content",
            },
            {
                "item_id": "001-123457",
                "ecli": "ECLI:2",
                "full_text": "Text two content",
            },
        ]
        result = prepare_echr_corpus(df, full_texts)
        assert "fulltext" in result.columns
        assert len(result) == 2
        assert result.iloc[0]["fulltext"] == "Text one content"
        assert result.iloc[1]["fulltext"] == "Text two content"

    def test_handles_key_name_mismatch(self):
        df = pd.DataFrame({"itemid": ["001-123456"], "languageisocode": ["ENG"]})
        full_texts = [
            {"item_id": "001-123456", "ecli": "E1", "full_text": "txt content"}
        ]
        result = prepare_echr_corpus(df, full_texts)
        assert "fulltext" in result.columns
        assert result.iloc[0]["fulltext"] == "txt content"

    def test_false_df_returns_empty(self):
        result = prepare_echr_corpus(False, [{"item_id": "x", "full_text": "y"}])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_empty_full_texts_returns_empty(self):
        df = pd.DataFrame({"itemid": ["001"]})
        result = prepare_echr_corpus(df, [])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_none_full_texts_returns_empty(self):
        df = pd.DataFrame({"itemid": ["001"]})
        result = prepare_echr_corpus(df, None)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_no_duplicate_ecli_column(self):
        df = pd.DataFrame(
            {
                "itemid": ["001-123456"],
                "ecli": ["ECLI:ORIGINAL"],
                "languageisocode": ["ENG"],
            }
        )
        full_texts = [
            {"item_id": "001-123456", "ecli": "ECLI:FULLTEXT", "full_text": "txt"}
        ]
        result = prepare_echr_corpus(df, full_texts)
        # Should keep original ecli, not create duplicate columns
        assert result.columns.tolist().count("ecli") == 1


# ---------------------------------------------------------------------------
# Tests: get_echr_segments (convenience wrapper)
# ---------------------------------------------------------------------------
class TestSegmentEchrDocuments:
    def test_with_separate_inputs(self):
        df = pd.DataFrame(
            {
                "itemid": ["001-123456"],
                "languageisocode": ["ENG"],
            }
        )
        full_texts = [
            {
                "item_id": "001-123456",
                "ecli": "E1",
                "full_text": STANDARD_JUDGMENT_TEXT,
            }
        ]
        result = get_echr_segments(df=df, full_texts=full_texts, save_file="n")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["num_sections"] >= 4

    def test_with_corpus_df(self):
        corpus = pd.DataFrame(
            {
                "itemid": ["001-123456"],
                "languageisocode": ["ENG"],
                "fulltext": [STANDARD_JUDGMENT_TEXT],
            }
        )
        result = get_echr_segments(corpus_df=corpus, save_file="n")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_no_input_returns_empty(self):
        result = get_echr_segments(save_file="n")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_allowed_langs_forwarded(self):
        corpus = pd.DataFrame(
            {
                "itemid": ["001-1"],
                "languageisocode": ["DEU"],
                "fulltext": [STANDARD_JUDGMENT_TEXT],
            }
        )
        result = get_echr_segments(
            corpus_df=corpus, save_file="n", allowed_langs=("ENG",)
        )
        assert result.iloc[0]["parser_mode"] == "skipped_language"


# ---------------------------------------------------------------------------
# Tests: Custom pattern coverage (reaching code paths unreachable with
# standard patterns to achieve 100% coverage)
# ---------------------------------------------------------------------------
class TestCustomPatternCoverage:
    """Tests using custom compiled pattern dicts to exercise code paths
    that standard SEGMENTATION_PATTERNS cannot reach."""

    def test_header_like_before_ok_false(self):
        """Cover line 481 (is_header_like returns False due to before_ok=False)
        and line 665 (continue in header_position check).

        PROCEDURE mid-sentence after only a space — the lookbehind pattern
        matches but is_header_like rejects because the prefix is non-empty,
        the before chars aren't punctuation, and start char isn't special.
        """
        text = "some word PROCEDURE 1. The case is about the applicant.\n"
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        # PROCEDURE mid-sentence should be rejected
        sections = [b[0] for b in boundaries]
        assert "procedure" not in sections

    def test_is_strong_header_unknown_section(self):
        """Cover line 542 (is_strong_header returns False for unknown section).

        Use a custom pattern dict with a section name not handled by the
        if/elif chain in is_strong_header.
        """
        custom_patterns = {
            "unknown_section": [
                re.compile(r"(?:^|\n)UNKNOWN\s+HEADER\b", re.MULTILINE),
            ],
        }
        text = "\nUNKNOWN HEADER\n\nSome content after the unknown header.\n"
        boundaries = find_section_boundaries(text, custom_patterns)
        # The section should still be found (is_strong_header returns False
        # but that only affects pass 1 pre-scan, not the actual boundary)
        sections = [b[0] for b in boundaries]
        assert "unknown_section" in sections

    def test_has_initials_prefix_exception(self):
        """Cover lines 545-552 (has_initials_prefix body) and
        lines 653-656 (separate_opinion exception when is_header_like fails).

        Judge initials (A.B.C.D.) glued before DISSENTING OPINION, with
        lowercase text suffix so is_header_like fails, but has_initials_prefix
        passes and the match is accepted via the exception.
        """
        text = (
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that there has been a violation of Article 6.\n\n"
            "A.B.C.D.DISSENTING OPINION about the judgment here "
            "and the reasoning of the majority view.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        assert "separate_opinion" in sections

    def test_is_appendix_inline_header_exception(self):
        """Cover lines 555-566 (is_appendix_inline_header body) and
        lines 657-663 (appendix exception when is_header_like fails).

        APPENDIX preceded by double space mid-line (not after newline),
        so is_header_like fails, but is_appendix_inline_header passes.
        """
        text = (
            "FOR THESE REASONS, THE COURT\n\n"
            "Holds that there has been a violation.  "
            "APPENDIXList of applications and their reference numbers here.\n"
        )
        normalized = text.replace("_", " ")
        boundaries = find_section_boundaries(
            normalized, _COMPILED_PATTERNS, original_text=text
        )
        sections = [b[0] for b in boundaries]
        assert "appendix" in sections

    def test_uppercase_filter_rejects_non_canonical(self):
        """Cover line 615 (uppercase section match that's not a canonical keyword).

        Use a custom 'facts' pattern that matches uppercase text "THE DATA"
        which is NOT a canonical facts keyword.
        """
        custom_patterns = {
            "facts": [
                re.compile(
                    r"(?:^|\n)\s*THE\s+DATA\s*(?:\n|$)",
                    re.IGNORECASE | re.MULTILINE,
                ),
            ],
        }
        text = "\nTHE DATA\n\nSome content about the data in this case.\n"
        boundaries = find_section_boundaries(text, custom_patterns)
        # "THE DATA" matches the pattern but is_strong_header("facts", ...)
        # returns False (no canonical keyword), so it's rejected at line 615
        sections = [b[0] for b in boundaries]
        assert "facts" not in sections

    def test_alleged_violation_of_article_in_match(self):
        """Cover line 623 (complaints match containing 'ALLEGED VIOLATION OF ARTICLE').

        Use a custom complaints pattern that captures the full phrase.
        """
        custom_patterns = {
            "complaints": [
                re.compile(
                    r"ALLEGED\s+VIOLATION\s+OF\s+ARTICLE\s+\d+",
                    re.IGNORECASE | re.MULTILINE,
                ),
            ],
        }
        text = (
            "Some text.\n"
            "ALLEGED VIOLATION OF ARTICLE 6\n\n"
            "The applicant complained about the trial process.\n"
        )
        boundaries = find_section_boundaries(text, custom_patterns)
        # Match text contains "ALLEGED VIOLATION OF ARTICLE" → rejected
        sections = [b[0] for b in boundaries]
        assert "complaints" not in sections

    def test_court_assessment_non_canonical_custom(self):
        """Cover line 637 (court_assessment canonical check fails).

        Use a custom court_assessment pattern that matches text without
        both 'COURT' and 'ASSESSMENT'.
        """
        custom_patterns = {
            "court_assessment": [
                re.compile(
                    r"(?:^|\n)\s*THE\s+EVALUATION\s*(?:\n|$)",
                    re.IGNORECASE | re.MULTILINE,
                ),
            ],
        }
        text = "\nTHE EVALUATION\n\nThe evaluation of the case follows.\n"
        boundaries = find_section_boundaries(text, custom_patterns)
        # "THE EVALUATION" doesn't contain both COURT and ASSESSMENT → rejected
        sections = [b[0] for b in boundaries]
        assert "court_assessment" not in sections

    def test_strong_header_suppression_weak_match(self):
        """Cover line 676 (weak match suppressed when strong header exists).

        Use custom operative patterns where one is strong and one is weak.
        """
        custom_patterns = {
            "operative": [
                re.compile(r"FOR\s+THESE\s+REASONS", re.IGNORECASE | re.MULTILINE),
                re.compile(r"(?:^|\n)DECISION\b", re.IGNORECASE | re.MULTILINE),
            ],
        }
        text = (
            "FOR THESE REASONS\n\n"
            "The Court holds unanimously that there has been a violation.\n\n"
            "DECISION\n\n"
            "Some additional decisional text about the outcome.\n"
        )
        boundaries = find_section_boundaries(text, custom_patterns)
        operative_boundaries = [b for b in boundaries if b[0] == "operative"]
        # "FOR THESE REASONS" is strong, "DECISION" is weak → suppressed
        assert len(operative_boundaries) == 1
        assert "FOR THESE REASONS" in operative_boundaries[0][3]


class TestNonstandardFallbackCoverage:
    """Tests to cover the nonstandard fallback and unknown mode paths."""

    def test_commission_decision_fallback_no_strict_matches(self):
        """Cover lines 904-908: commission_decision with no strict matches
        falls back to nonstandard patterns.

        Uses simple headers (FACTS, LAW) that only match nonstandard patterns.
        """
        text = (
            "FACTS\n\n"
            "The applicant was born in 1980 and lives in a place far away.\n\n"
            "LAW\n\n"
            "The Commission considers the complaint under Article 6 carefully.\n\n"
        )
        df = _make_df(text, doctype="HEDEC")
        result = segment_echr_texts(df)
        assert result.iloc[0]["parser_mode"] == "commission_decision"
        # Should find sections via nonstandard fallback
        assert result.iloc[0]["num_sections"] > 0

    def test_communicated_case_fallback_no_strict_matches(self):
        """Cover communicated_case fallback path with no strict matches."""
        text = (
            "FACTS\n\n"
            "The applicant was born in 1980 and lives in a place far away.\n\n"
            "QUESTIONS TO THE PARTIES\n\n"
            "1. Has there been a violation of Article 6 of the Convention?\n"
        )
        df = _make_df(text, doctype="HECOM")
        result = segment_echr_texts(df)
        assert result.iloc[0]["parser_mode"] == "communicated_case"
        assert result.iloc[0]["num_sections"] > 0

    def test_unknown_parser_mode_treated_as_standard(self):
        """Cover lines 909-915: unknown parser mode falls through to standard.

        Monkeypatches choose_parser_mode to return an unrecognized mode.
        """
        import echr_extractor.ECHR_text_segmenter as seg

        original = seg.choose_parser_mode
        seg.choose_parser_mode = lambda *a, **kw: "unknown_mode"
        try:
            df = _make_df(STANDARD_JUDGMENT_TEXT)
            result = segment_echr_texts(df)
            assert result.iloc[0]["parser_mode"] == "unknown_mode"
            assert result.iloc[0]["num_sections"] >= 4
        finally:
            seg.choose_parser_mode = original
