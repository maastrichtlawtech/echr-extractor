from unittest.mock import MagicMock, patch

import pandas as pd

from echr_extractor.ECHR_html_downloader import download_full_text_main


def test_configured_timeout_is_passed_to_requests():
    response = MagicMock(status_code=200, text="<p>Judgment</p>")
    response.raise_for_status.return_value = None
    df = pd.DataFrame({"itemid": ["001-1"], "ecli": ["ECLI:1"]})

    with patch(
        "echr_extractor.ECHR_html_downloader.requests.get",
        return_value=response,
    ) as get:
        result = download_full_text_main(df, threads=1, timeout=91)

    assert result[0]["full_text"] == "Judgment"
    get.assert_called_once_with(
        "https://hudoc.echr.coe.int/app/conversion/docx/html/body?library=ECHR&id=001-1",
        timeout=91,
    )


def test_empty_dataframe_returns_without_starting_threads():
    df = pd.DataFrame({"itemid": [], "ecli": []})

    assert download_full_text_main(df, threads=4) == []


def test_requested_threads_are_capped_for_hudoc():
    df = pd.DataFrame(
        {
            "itemid": [f"001-{item}" for item in range(8)],
            "ecli": [f"ECLI:{item}" for item in range(8)],
        }
    )
    response = MagicMock(status_code=204, text="")
    response.raise_for_status.return_value = None

    with patch(
        "echr_extractor.ECHR_html_downloader.requests.get",
        return_value=response,
    ), patch(
        "echr_extractor.ECHR_html_downloader.threading.Thread",
        wraps=__import__("threading").Thread,
    ) as thread:
        download_full_text_main(df, threads=10)

    assert thread.call_count == 4
