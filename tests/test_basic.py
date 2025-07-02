"""Basic tests for the ECHR extractor package."""

from unittest.mock import patch
import pandas as pd

from echr_extractor import get_echr


class TestECHRExtractor:
    """Test cases for ECHR extractor main functions."""

    @patch("echr_extractor.echr.get_echr_metadata")
    def test_get_echr_basic(self, mock_get_metadata):
        """Test basic ECHR metadata extraction."""
        # Mock the metadata harvester to return sample data
        sample_df = pd.DataFrame(
            {"itemid": ["001-123456"], "title": ["Test Case"], "kpdate": ["2023-01-01"]}
        )
        mock_get_metadata.return_value = sample_df

        # Call the function
        result = get_echr(start_id=0, count=1, save_file="n")

        # Verify the result
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["itemid"] == "001-123456"

        # Verify the mock was called with correct parameters
        mock_get_metadata.assert_called_once()

    def test_count_overrides_end_id(self):
        """Test that count parameter overrides end_id."""
        with patch("echr_extractor.echr.get_echr_metadata") as mock_get_metadata:
            mock_get_metadata.return_value = pd.DataFrame()

            # This should set end_id to 50 (start_id + count)
            get_echr(start_id=10, end_id=100, count=40, save_file="n")

            # Check that the metadata harvester was called with end_id=50
            args, kwargs = mock_get_metadata.call_args
            assert kwargs.get("end_id") == 50

    def test_default_language(self):
        """Test that default language is set correctly."""
        with patch("echr_extractor.echr.get_echr_metadata") as mock_get_metadata:
            mock_get_metadata.return_value = pd.DataFrame()

            get_echr(save_file="n")

            args, kwargs = mock_get_metadata.call_args
            assert kwargs.get("language") == ["ENG"]
