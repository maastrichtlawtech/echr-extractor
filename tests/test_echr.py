"""Test the main ECHR extractor functions."""

from unittest.mock import patch

import pandas as pd

from echr_extractor import (
    get_echr,
    get_echr_extra,
    get_echr_segments,
    get_nodes_edges,
    prepare_segmentation_corpus,
    segment_document,
    segment_documents,
)
from echr_extractor.echr import prepare_echr_corpus
from echr_extractor.segmentation import SEGMENT_OUTPUT_COLUMNS


STANDARD_JUDGMENT_TEXT = (
    "HEADER INFO\n\n"
    "PROCEDURE\n\n"
    "1. The case originated in an application filed against the State.\n\n"
    "THE FACTS\n\n"
    "2. The applicant was born in 1980 and lives in a city.\n\n"
    "THE LAW\n\n"
    "3. The Court notes that Article 6 of the Convention applies.\n\n"
    "FOR THESE REASONS, THE COURT\n\n"
    "Holds that there has been a violation of Article 6.\n"
)


class TestGetECHR:
    """Test the get_echr function."""

    @patch("echr_extractor.echr.get_echr_metadata")
    def test_get_echr_basic_functionality(self, mock_get_metadata):
        """Test basic ECHR metadata extraction."""
        # Setup mock data
        sample_df = pd.DataFrame(
            {
                "itemid": ["001-123456", "001-123457"],
                "title": ["Test Case 1", "Test Case 2"],
                "kpdate": ["2023-01-01", "2023-01-02"],
            }
        )
        mock_get_metadata.return_value = sample_df

        # Call function
        result = get_echr(start_id=0, count=2, save_file="n")

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert result.iloc[0]["itemid"] == "001-123456"
        assert result.iloc[1]["itemid"] == "001-123457"
        mock_get_metadata.assert_called_once()

    @patch("echr_extractor.echr.get_echr_metadata")
    def test_count_parameter(self, mock_get_metadata):
        """Test that count parameter sets end_id correctly."""
        mock_get_metadata.return_value = pd.DataFrame()

        get_echr(start_id=10, end_id=100, count=40, save_file="n")

        args, kwargs = mock_get_metadata.call_args
        assert kwargs.get("end_id") == 50  # start_id + count

    @patch("echr_extractor.echr.get_echr_metadata")
    def test_default_language(self, mock_get_metadata):
        """Test default language setting."""
        mock_get_metadata.return_value = pd.DataFrame()

        get_echr(save_file="n")

        args, kwargs = mock_get_metadata.call_args
        assert kwargs.get("language") == ["ENG"]

    @patch("echr_extractor.echr.get_echr_metadata")
    def test_custom_language(self, mock_get_metadata):
        """Test custom language setting."""
        mock_get_metadata.return_value = pd.DataFrame()

        get_echr(language=["FRE", "GER"], save_file="n")

        args, kwargs = mock_get_metadata.call_args
        assert kwargs.get("language") == ["FRE", "GER"]

    @patch("echr_extractor.echr.get_echr_metadata")
    def test_metadata_harvester_failure(self, mock_get_metadata):
        """Test handling when metadata harvester returns False."""
        mock_get_metadata.return_value = False

        result = get_echr(save_file="n")

        assert result is False


class TestGetECHRExtra:
    """Test the get_echr_extra function."""

    @patch("echr_extractor.echr.download_full_text_main")
    @patch("echr_extractor.echr.get_echr_metadata")
    def test_get_echr_extra_basic(self, mock_get_metadata, mock_download_text):
        """Test ECHR metadata + full text extraction."""
        # Setup mocks
        sample_df = pd.DataFrame(
            {
                "itemid": ["001-123456"],
                "title": ["Test Case"],
            }
        )
        mock_get_metadata.return_value = sample_df
        mock_download_text.return_value = [
            {"itemid": "001-123456", "text": "Full text"}
        ]

        # Call function
        df_result, text_result = get_echr_extra(count=1, save_file="n")

        # Assertions
        assert isinstance(df_result, pd.DataFrame)
        assert isinstance(text_result, list)
        assert len(text_result) == 1
        assert text_result[0]["itemid"] == "001-123456"

    @patch("echr_extractor.echr.download_full_text_main")
    @patch("echr_extractor.echr.get_echr_metadata")
    def test_get_echr_extra_saved_filenames_match_get_echr(
        self, mock_get_metadata, mock_download_text, tmp_path, monkeypatch
    ):
        """Regression: with count=N, get_echr_extra used to save files
        named 0-ALL while get_echr saved 0-N for the same parameters."""
        monkeypatch.chdir(tmp_path)
        mock_get_metadata.return_value = pd.DataFrame(
            {"itemid": ["001-1", "001-2"]}
        )
        mock_download_text.return_value = [{"itemid": "001-1", "text": "t"}]

        get_echr_extra(count=2, save_file="y")

        assert (tmp_path / "data" / "echr_metadata_0-2_dates_START-END.csv").exists()
        assert (
            tmp_path / "data" / "echr_full_text_0-2_dates_START-END.json"
        ).exists()

    @patch("echr_extractor.echr.download_full_text_main")
    @patch("echr_extractor.echr.get_echr_metadata")
    def test_get_echr_extra_metadata_failure(
        self, mock_get_metadata, mock_download_text
    ):
        """Test handling when metadata extraction fails."""
        mock_get_metadata.return_value = False

        df_result, text_result = get_echr_extra(save_file="n")

        assert df_result is False
        assert text_result is False
        mock_download_text.assert_not_called()


class TestGetNodesEdges:
    """Test the get_nodes_edges function."""

    @patch("echr_extractor.echr.echr_nodes_edges")
    def test_get_nodes_edges_with_dataframe(self, mock_nodes_edges):
        """Test nodes/edges generation with DataFrame input."""
        # Setup mock
        sample_df = pd.DataFrame({"itemid": ["001-123456"]})
        mock_nodes = pd.DataFrame({"node_id": [1], "itemid": ["001-123456"]})
        mock_edges = pd.DataFrame({"source": [1], "target": [2]})
        mock_missing = pd.DataFrame({"missing_references": []})
        mock_nodes_edges.return_value = (mock_nodes, mock_edges, mock_missing)

        # Call function
        nodes, edges, missing_df = get_nodes_edges(df=sample_df, save_file="n")

        # Assertions
        assert isinstance(nodes, pd.DataFrame)
        assert isinstance(edges, pd.DataFrame)
        assert isinstance(missing_df, pd.DataFrame)
        mock_nodes_edges.assert_called_once_with(metadata_path=None, data=sample_df)

    @patch("echr_extractor.echr.echr_nodes_edges")
    def test_get_nodes_edges_with_file_path(self, mock_nodes_edges):
        """Test nodes/edges generation with file path input."""
        # Setup mock
        mock_nodes = pd.DataFrame({"node_id": [1]})
        mock_edges = pd.DataFrame({"source": [1], "target": [2]})
        mock_missing = pd.DataFrame({"missing_references": []})
        mock_nodes_edges.return_value = (mock_nodes, mock_edges, mock_missing)

        # Call function
        nodes, edges, missing_df = get_nodes_edges(
            metadata_path="test.csv", save_file="n"
        )

        # Assertions
        assert isinstance(nodes, pd.DataFrame)
        assert isinstance(edges, pd.DataFrame)
        mock_nodes_edges.assert_called_once_with(metadata_path="test.csv", data=None)


class TestParameterValidation:
    """Test parameter validation and edge cases."""

    def test_invalid_save_file_parameter(self):
        """Test with invalid save_file parameter."""
        with patch("echr_extractor.echr.get_echr_metadata") as mock_get_metadata:
            mock_get_metadata.return_value = pd.DataFrame()

            # Should work with valid parameters
            result = get_echr(save_file="n")
            assert isinstance(result, pd.DataFrame)

    def test_empty_dataframe_handling(self):
        """Test handling of empty DataFrame results."""
        with patch("echr_extractor.echr.get_echr_metadata") as mock_get_metadata:
            mock_get_metadata.return_value = pd.DataFrame()

            result = get_echr(save_file="n")
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0


class TestSegmentationWorkflow:
    """Test the package-level segmentation workflow helpers."""

    def test_prepare_echr_corpus_merges_full_texts(self):
        df = pd.DataFrame(
            {
                "itemid": ["001-1"],
                "ecli": ["ECLI:ORIGINAL"],
                "languageisocode": ["ENG"],
                "doctype": ["HEJUD"],
            }
        )
        full_texts = [
            {
                "item_id": "001-1",
                "ecli": "ECLI:FULLTEXT",
                "full_text": STANDARD_JUDGMENT_TEXT,
            }
        ]

        result = prepare_echr_corpus(df, full_texts)

        assert len(result) == 1
        assert result.iloc[0]["fulltext"] == STANDARD_JUDGMENT_TEXT
        assert result.columns.tolist().count("ecli") == 1
        assert result.iloc[0]["ecli"] == "ECLI:ORIGINAL"

    def test_prepare_echr_corpus_preserves_metadata_columns(self):
        """Regression: the docstring promises 'metadata columns plus
        fulltext', but extra columns used to be dropped in the merge."""
        df = pd.DataFrame(
            {
                "itemid": ["001-1"],
                "ecli": ["ECLI:X"],
                "languageisocode": ["ENG"],
                "appno": ["123/45"],
                "article": ["6"],
                "scl": ["Some v. Case, 1 January 2000"],
            }
        )
        full_texts = [{"item_id": "001-1", "full_text": STANDARD_JUDGMENT_TEXT}]

        result = prepare_echr_corpus(df, full_texts)

        assert set(df.columns) <= set(result.columns)
        assert result.iloc[0]["appno"] == "123/45"
        assert result.iloc[0]["scl"] == "Some v. Case, 1 January 2000"

    def test_prepare_echr_corpus_empty_inputs_return_empty_dataframe(self):
        result = prepare_echr_corpus(False, None)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_prepare_segmentation_corpus_supports_document_input(self):
        corpus = prepare_segmentation_corpus(document=STANDARD_JUDGMENT_TEXT)

        assert corpus.iloc[0]["itemid"] == "doc-1"
        assert corpus.iloc[0]["languageisocode"] == "ENG"
        assert corpus.iloc[0]["fulltext"] == STANDARD_JUDGMENT_TEXT

    def test_prepare_segmentation_corpus_normalizes_language_keys_before_merge(self):
        metadata_df = pd.DataFrame(
            {
                "itemid": ["001-1"],
                "languageisocode": ["ENG"],
                "doctype": ["HEJUD"],
            }
        )
        full_texts = [
            {
                "item_id": "001-1",
                "languageisocode": "eng",
                "full_text": STANDARD_JUDGMENT_TEXT,
            }
        ]

        corpus = prepare_segmentation_corpus(df=metadata_df, full_texts=full_texts)

        assert corpus.iloc[0]["languageisocode"] == "ENG"
        assert corpus.iloc[0]["fulltext"] == STANDARD_JUDGMENT_TEXT

    def test_prepare_segmentation_corpus_falls_back_to_itemid_when_language_match_is_unavailable(self):
        metadata_df = pd.DataFrame(
            {
                "itemid": ["001-1"],
                "languageisocode": ["ENG"],
                "doctype": ["HEJUD"],
            }
        )
        full_texts = [
            {
                "item_id": "001-1",
                "languageisocode": "FRE",
                "full_text": STANDARD_JUDGMENT_TEXT,
            }
        ]

        corpus = prepare_segmentation_corpus(df=metadata_df, full_texts=full_texts)

        assert corpus.iloc[0]["fulltext"] == STANDARD_JUDGMENT_TEXT

    def test_segment_document_returns_package_shaped_record(self):
        result = segment_document(
            text=STANDARD_JUDGMENT_TEXT,
            itemid="001-1",
            languageisocode="ENG",
        )

        assert list(result.keys()) == SEGMENT_OUTPUT_COLUMNS
        assert result["itemid"] == "001-1"
        assert result["parser_mode"] == "standard"
        assert result["procedure"] is not None
        assert result["facts"] is not None
        assert result["law"] is not None
        assert result["operative"] is not None
        assert result["error"] is None

    def test_segment_documents_supports_dataframe_workflow(self):
        metadata_df = pd.DataFrame(
            {
                "itemid": ["001-1"],
                "languageisocode": ["ENG"],
                "doctype": ["HEJUD"],
                "doctypebranch": ["CHAMBER"],
            }
        )
        full_texts = [{"item_id": "001-1", "full_text": STANDARD_JUDGMENT_TEXT}]

        result = segment_documents(df=metadata_df, full_texts=full_texts)

        assert list(result.columns) == SEGMENT_OUTPUT_COLUMNS
        assert len(result) == 1
        assert result.iloc[0]["parser_mode"] == "standard"
        assert result.iloc[0]["num_sections"] >= 4

    def test_segment_documents_supports_premerged_corpus_dataframe(self):
        corpus_df = pd.DataFrame(
            {
                "itemid": ["001-1"],
                "languageisocode": ["ENG"],
                "ecli": ["ECLI:CE:ECHR:2024:TEST"],
                "doctype": ["HEJUD"],
                "doctypebranch": ["CHAMBER"],
                "fulltext": [STANDARD_JUDGMENT_TEXT],
            }
        )

        result = segment_documents(corpus_df=corpus_df)

        assert len(result) == 1
        assert result.iloc[0]["ecli"] == "ECLI:CE:ECHR:2024:TEST"
        assert result.iloc[0]["procedure"] is not None

    def test_get_echr_segments_supports_document_input(self):
        result = get_echr_segments(document=STANDARD_JUDGMENT_TEXT, save_file="n")

        assert len(result) == 1
        assert result.iloc[0]["itemid"] == "doc-1"
        assert result.iloc[0]["parser_mode"] == "standard"

    def test_get_echr_segments_forwards_allowed_langs(self):
        corpus = pd.DataFrame(
            {
                "itemid": ["001-1"],
                "languageisocode": ["DEU"],
                "fulltext": [STANDARD_JUDGMENT_TEXT],
            }
        )

        result = get_echr_segments(
            corpus_df=corpus,
            save_file="n",
            allowed_langs=("ENG",),
        )

        assert result.iloc[0]["parser_mode"] == "skipped_language"
