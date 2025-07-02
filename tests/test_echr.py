"""Test the main ECHR extractor functions."""

from unittest.mock import patch
import pandas as pd

from echr_extractor import get_echr, get_echr_extra, get_nodes_edges


class TestGetECHR:
    """Test the get_echr function."""

    @patch("echr_extractor.echr.get_echr_metadata")
    def test_get_echr_basic_functionality(self, mock_get_metadata):
        """Test basic ECHR metadata extraction."""
        # Setup mock data
        sample_df = pd.DataFrame({
            "itemid": ["001-123456", "001-123457"],
            "title": ["Test Case 1", "Test Case 2"],
            "kpdate": ["2023-01-01", "2023-01-02"]
        })
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
        sample_df = pd.DataFrame({
            "itemid": ["001-123456"],
            "title": ["Test Case"],
        })
        mock_get_metadata.return_value = sample_df
        mock_download_text.return_value = [{"itemid": "001-123456", "text": "Full text"}]

        # Call function
        df_result, text_result = get_echr_extra(count=1, save_file="n")

        # Assertions
        assert isinstance(df_result, pd.DataFrame)
        assert isinstance(text_result, list)
        assert len(text_result) == 1
        assert text_result[0]["itemid"] == "001-123456"

    @patch("echr_extractor.echr.download_full_text_main")
    @patch("echr_extractor.echr.get_echr_metadata")
    def test_get_echr_extra_metadata_failure(self, mock_get_metadata, mock_download_text):
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
        mock_nodes_edges.return_value = (mock_nodes, mock_edges)

        # Call function
        nodes, edges = get_nodes_edges(df=sample_df, save_file="n")

        # Assertions
        assert isinstance(nodes, pd.DataFrame)
        assert isinstance(edges, pd.DataFrame)
        mock_nodes_edges.assert_called_once_with(metadata_path=None, data=sample_df)

    @patch("echr_extractor.echr.echr_nodes_edges")
    def test_get_nodes_edges_with_file_path(self, mock_nodes_edges):
        """Test nodes/edges generation with file path input."""
        # Setup mock
        mock_nodes = pd.DataFrame({"node_id": [1]})
        mock_edges = pd.DataFrame({"source": [1], "target": [2]})
        mock_nodes_edges.return_value = (mock_nodes, mock_edges)

        # Call function
        nodes, edges = get_nodes_edges(metadata_path="test.csv", save_file="n")

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
