"""Test configuration and fixtures."""

import pytest
import pandas as pd


@pytest.fixture
def sample_metadata():
    """Sample ECHR metadata for testing."""
    return pd.DataFrame({
        'itemid': ['001-123456', '001-123457'],
        'appno': ['12345/20', '12346/20'],
        'title': ['Test Case 1', 'Test Case 2'],
        'kpdate': ['2023-01-01', '2023-01-02'],
        'languageisocode': ['ENG', 'ENG']
    })


@pytest.fixture
def sample_full_text():
    """Sample full text data for testing."""
    return [
        {
            'itemid': '001-123456',
            'text': 'This is the full text of case 1.'
        },
        {
            'itemid': '001-123457', 
            'text': 'This is the full text of case 2.'
        }
    ]
