"""Test configuration and fixtures."""

import os

import pandas as pd
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run tests that hit the real HUDOC API",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: test performs real HUDOC API requests "
        "(skipped unless --run-live or ECHR_RUN_LIVE=1)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live") or os.environ.get("ECHR_RUN_LIVE") == "1":
        return
    skip_live = pytest.mark.skip(reason="live HUDOC test: pass --run-live to enable")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def sample_metadata():
    """Sample ECHR metadata for testing."""
    return pd.DataFrame(
        {
            "itemid": ["001-123456", "001-123457"],
            "appno": ["12345/20", "12346/20"],
            "title": ["Test Case 1", "Test Case 2"],
            "kpdate": ["2023-01-01", "2023-01-02"],
            "languageisocode": ["ENG", "ENG"],
        }
    )


@pytest.fixture
def sample_full_text():
    """Sample full text data for testing."""
    return [
        {"itemid": "001-123456", "text": "This is the full text of case 1."},
        {"itemid": "001-123457", "text": "This is the full text of case 2."},
    ]
