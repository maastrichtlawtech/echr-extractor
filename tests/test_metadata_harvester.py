"""Unit tests for the metadata harvester query building and fetching.

These tests exercise the real query-construction code (link_to_query,
determine_meta_url, get_echr_metadata) without network access; HTTP calls
are mocked at the requests layer. Live end-to-end coverage lives in
test_live_hudoc.py.
"""

import urllib.parse
from unittest.mock import MagicMock, patch

import pandas as pd

from echr_extractor.ECHR_metadata_harvester import (
    basic_function,
    determine_meta_url,
    get_date_ranges,
    get_echr_metadata,
    link_to_query,
    split_date_range,
)


def hudoc_link(fragment):
    """Build a HUDOC advanced-search link from a raw JSON fragment."""
    return "https://hudoc.echr.coe.int/eng#" + urllib.parse.quote(fragment)


class TestBasicFunction:
    def test_single_value(self):
        assert basic_function("docname", ["turkey"]) == (
            '((docname="turkey") OR (docname:"turkey"))'
        )

    def test_multiple_values_joined_with_or(self):
        query = basic_function("languageisocode", ["ENG", "FRE"])
        assert '(languageisocode="ENG") OR (languageisocode:"ENG")' in query
        assert '(languageisocode="FRE") OR (languageisocode:"FRE")' in query
        assert query.count(" OR ") == 3


class TestGetDateRanges:
    def test_no_dates_returns_single_range(self):
        assert get_date_ranges(None, None) == [(None, None)]

    def test_range_within_batch_size(self):
        assert get_date_ranges("2023-01-01", "2023-06-30", days_per_batch=365) == [
            ("2023-01-01", "2023-06-30")
        ]

    def test_range_split_into_batches(self):
        ranges = get_date_ranges("2020-01-01", "2021-12-31", days_per_batch=365)
        assert len(ranges) == 3
        assert ranges[0] == ("2020-01-01", "2020-12-30")
        assert ranges[1] == ("2020-12-31", "2021-12-30")
        assert ranges[2] == ("2021-12-31", "2021-12-31")

    def test_single_day_range_is_not_dropped(self):
        """Regression: a one-day range used to produce zero batches."""
        assert get_date_ranges("2023-05-01", "2023-05-01") == [
            ("2023-05-01", "2023-05-01")
        ]

    def test_final_day_remainder_is_not_dropped(self):
        """Regression: a remainder of exactly one day used to be lost."""
        ranges = get_date_ranges("2020-01-01", "2020-01-11", days_per_batch=10)
        assert ranges == [
            ("2020-01-01", "2020-01-10"),
            ("2020-01-11", "2020-01-11"),
        ]

    def test_batches_are_contiguous_without_overlap(self):
        ranges = get_date_ranges("2019-01-01", "2022-12-31", days_per_batch=180)
        for (_, prev_end), (next_start, _) in zip(ranges, ranges[1:]):
            prev = pd.Timestamp(prev_end)
            nxt = pd.Timestamp(next_start)
            assert (nxt - prev).days == 1


class TestSplitDateRange:
    def test_bisects_without_gap_or_overlap(self):
        halves = split_date_range("2020-01-01", "2020-12-31")
        assert halves[0][0] == "2020-01-01"
        assert halves[1][1] == "2020-12-31"
        gap = pd.Timestamp(halves[1][0]) - pd.Timestamp(halves[0][1])
        assert gap.days == 1

    def test_open_ends_default_to_full_history(self):
        halves = split_date_range(None, None)
        assert halves[0][0] == "1900-01-01"
        assert halves[1][1] == pd.Timestamp.today().strftime("%Y-%m-%d")

    def test_single_day_cannot_be_split(self):
        assert split_date_range("2020-01-01", "2020-01-01") is None


class TestLinkToQuery:
    def test_mapped_key_docname(self):
        query = link_to_query(hudoc_link('{"docname":["turkey"]}'))
        assert '(docname="turkey") OR (docname:"turkey")' in query

    def test_itemid_link(self):
        query = link_to_query(hudoc_link('{"itemid":["001-100448"]}'))
        assert '(itemid="001-100448") OR (itemid:"001-100448")' in query

    def test_kpdate_range(self):
        query = link_to_query(hudoc_link('{"kpdate":["2020-01-01","2020-12-31"]}'))
        assert 'kpdate>="2020-01-01" AND kpdate<="2020-12-31"' in query

    def test_kpdate_open_start_defaults_to_1900(self):
        query = link_to_query(hudoc_link('{"kpdate":["","2020-12-31"]}'))
        assert 'kpdate>="1900-01-01"' in query

    def test_fulltext_terms(self):
        query = link_to_query(hudoc_link('{"fulltext":["climate"]}'))
        assert "(climate)" in query

    def test_languageisocode_filter(self):
        query = link_to_query(hudoc_link('{"languageisocode":["FRE"]}'))
        assert '(languageisocode="FRE") OR (languageisocode:"FRE")' in query

    def test_multiple_filters_joined_with_and(self):
        query = link_to_query(
            hudoc_link('{"docname":["turkey"],"kpdate":["2020-01-01","2020-12-31"]}')
        )
        docname_part = query.index("docname=")
        kpdate_part = query.index("kpdate>=")
        assert " AND " in query[docname_part:kpdate_part]

    def test_sort_key_is_ignored(self):
        query = link_to_query(
            hudoc_link('{"docname":["turkey"],"sort":["kpdate Descending"]}')
        )
        assert "Descending&" not in query.replace("itemid%20Ascending", "")
        assert '(docname="turkey")' in query

    def test_unmapped_keys_fall_back_to_basic_filter(self):
        """Regression: article/respondent/etc. filters must be applied.

        These keys are not in query_map; they used to crash (TypeError)
        after the batching rewrite, and were then silently dropped, which
        made link-based filtered fetches return the whole database.
        """
        query = link_to_query(hudoc_link('{"article":["10"],"respondent":["NLD"]}'))
        assert '(article="10") OR (article:"10")' in query
        assert '(respondent="NLD") OR (respondent:"NLD")' in query

    def test_unmapped_violation_and_importance_filters(self):
        query = link_to_query(hudoc_link('{"violation":["10"],"importance":["1"]}'))
        assert '(violation="10")' in query
        assert '(importance="1")' in query

    def test_body_section_filter(self):
        query = link_to_query(hudoc_link('{"bodylaw":["proportionality"]}'))
        assert '"THE LAW" ONEAR(n=1000) proportionality' in query

    def test_query_excludes_press_releases(self):
        query = link_to_query(hudoc_link('{"docname":["turkey"]}'))
        assert "NOT (doctype=PR OR doctype=HFCOMOLD OR doctype=HECOMOLD)" in query

    def test_placeholders_preserved_for_pagination(self):
        query = link_to_query(hudoc_link('{"docname":["turkey"]}'))
        assert "{select}" in query
        assert "{start}" in query
        assert "{length}" in query


class TestDetermineMetaUrl:
    def test_query_payload_takes_precedence(self):
        url = determine_meta_url("some-link", "(contentsitename=ECHR)", None, None)
        assert "query=(contentsitename=ECHR)" in url
        assert "{select}" in url and "{start}" in url and "{length}" in url

    def test_link_path_delegates_to_link_to_query(self):
        link = hudoc_link('{"docname":["turkey"]}')
        assert determine_meta_url(link, None, None, None) == link_to_query(link)

    def test_default_url_has_language_placeholder_and_collections(self):
        url = determine_meta_url(None, None, None, None)
        assert "lang_inputter" in url
        for collection in ("JUDGMENTS", "COMMUNICATEDCASES", "DECISIONS", "CLIN"):
            assert f'documentcollectionid2:"{collection}"' in url

    def test_default_url_excludes_press_releases(self):
        """Regression: press releases (doctype=PR) slipped into default
        fetches because HUDOC matches PRESS;CHAMBERJUDGMENTS against
        'JUDGMENTS'. The link path already excluded them."""
        url = determine_meta_url(None, None, None, None)
        assert "NOT (doctype=PR OR doctype=HFCOMOLD OR doctype=HECOMOLD)" in url

    def test_default_url_no_dates_has_no_kpdate(self):
        assert "kpdate" not in determine_meta_url(None, None, None, None)

    def test_default_url_with_date_range(self):
        url = determine_meta_url(None, None, "2020-01-01", "2020-12-31")
        assert '(kpdate>="2020-01-01" AND kpdate<="2020-12-31")' in url

    def test_default_url_start_date_only_ends_today(self):
        url = determine_meta_url(None, None, "2020-01-01", None)
        assert 'kpdate>="2020-01-01"' in url
        assert "kpdate<=" in url

    def test_default_url_end_date_only_starts_1900(self):
        url = determine_meta_url(None, None, None, "2020-12-31")
        assert 'kpdate>="1900-01-01"' in url
        assert 'kpdate<="2020-12-31"' in url


def fake_response(resultcount, columns_list):
    """Build a mock requests.Response for the HUDOC results endpoint."""
    response = MagicMock()
    response.json.return_value = {
        "resultcount": resultcount,
        "results": [{"columns": c} for c in columns_list],
    }
    response.raise_for_status.return_value = None
    return response


def make_record(i):
    return {"itemid": f"001-{i}", "docname": f"CASE {i}", "languageisocode": "ENG"}


class TestGetEchrMetadata:
    """Fetching logic with the HTTP layer mocked out."""

    def run(self, responses, **kwargs):
        defaults = dict(
            start_id=0,
            end_id=None,
            verbose=False,
            fields=["itemid", "docname", "languageisocode"],
            start_date=None,
            end_date=None,
            link=None,
            language=["ENG"],
            query_payload=None,
            progress_bar=False,
        )
        defaults.update(kwargs)
        with patch(
            "echr_extractor.ECHR_metadata_harvester.requests.get",
            side_effect=responses,
        ) as mock_get:
            result = get_echr_metadata(**defaults)
        return result, mock_get

    def test_returns_dataframe_with_records(self):
        records = [make_record(i) for i in range(3)]
        responses = [fake_response(3, []), fake_response(3, records)]
        df, _ = self.run(responses)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert list(df["itemid"]) == ["001-0", "001-1", "001-2"]

    def test_returns_false_when_no_results(self):
        df, _ = self.run([fake_response(0, [])])
        assert df is False

    def test_returns_false_when_all_requests_fail(self):
        import requests as requests_module

        def raise_error(*args, **kwargs):
            raise requests_module.exceptions.ConnectionError("down")

        with patch(
            "echr_extractor.ECHR_metadata_harvester.requests.get",
            side_effect=raise_error,
        ), patch("echr_extractor.ECHR_metadata_harvester.time.sleep"):
            result = get_echr_metadata(
                start_id=0,
                end_id=None,
                verbose=False,
                fields=["itemid"],
                start_date=None,
                end_date=None,
                link=None,
                language=["ENG"],
                query_payload=None,
                retry_attempts=0,
                max_attempts=1,
                progress_bar=False,
            )
        assert result is False

    def test_pagination_respects_batch_size(self):
        batch1 = [make_record(i) for i in range(2)]
        batch2 = [make_record(i) for i in range(2, 4)]
        responses = [
            fake_response(4, []),
            fake_response(4, batch1),
            fake_response(4, batch2),
        ]
        df, mock_get = self.run(responses, batch_size=2)
        assert len(df) == 4
        urls = [call.args[0] for call in mock_get.call_args_list]
        assert "start=0&length=2" in urls[1]
        assert "start=2&length=2" in urls[2]

    def test_end_id_caps_number_of_records(self):
        records = [make_record(i) for i in range(2)]
        responses = [fake_response(100, []), fake_response(100, records)]
        df, mock_get = self.run(responses, end_id=2)
        urls = [call.args[0] for call in mock_get.call_args_list]
        assert "start=0&length=2" in urls[1]
        assert len(df) == 2

    def test_language_filter_in_url(self):
        responses = [fake_response(1, []), fake_response(1, [make_record(0)])]
        _, mock_get = self.run(responses, language=["FRE", "GER"])
        url = mock_get.call_args_list[0].args[0]
        assert 'languageisocode="FRE"' in url
        assert 'languageisocode="GER"' in url

    def test_date_filter_in_url(self):
        responses = [fake_response(1, []), fake_response(1, [make_record(0)])]
        _, mock_get = self.run(
            responses, start_date="2023-01-01", end_date="2023-06-30"
        )
        url = mock_get.call_args_list[0].args[0]
        assert "kpdate>=%222023-01-01%22" in url
        assert "kpdate<=%222023-06-30%22" in url

    def test_date_batching_issues_one_query_per_range(self):
        responses = [
            fake_response(1, []),
            fake_response(1, [make_record(0)]),
            fake_response(1, []),
            fake_response(1, [make_record(1)]),
        ]
        df, mock_get = self.run(
            responses,
            start_date="2020-01-01",
            end_date="2020-12-31",
            days_per_batch=200,
        )
        assert len(df) == 2
        urls = [call.args[0] for call in mock_get.call_args_list]
        assert "2020-01-01" in urls[0] and "2020-07-18" in urls[0]
        assert "2020-07-19" in urls[2] and "2020-12-31" in urls[2]

    def test_end_id_caps_total_across_date_batches(self):
        """Regression: end_id/count used to be applied per date batch,
        so count=10 over 4 batches returned up to 40 records."""
        records = [make_record(i) for i in range(10)]
        responses = []
        for _ in range(4):
            responses.append(fake_response(100, []))
            responses.append(fake_response(100, records))
        df, _ = self.run(
            responses,
            end_id=10,
            start_date="2020-01-01",
            end_date="2020-12-31",
            days_per_batch=100,
        )
        assert len(df) == 10

    def test_start_id_not_applied_to_later_batch_after_failure(self):
        """Regression: when the first date window FAILS, start_id must
        be consumed rather than shifted onto the next window — that
        window's records were never meant to be skipped."""
        import requests as requests_module

        records = [make_record(i) for i in range(3)]
        responses = [
            requests_module.exceptions.ConnectionError("down"),  # window 1
            fake_response(3, []),  # window 2 count
            fake_response(3, records),  # window 2 fetch
        ]
        df, mock_get = self.run(
            responses,
            start_id=2,
            start_date="2020-01-01",
            end_date="2020-12-31",
            days_per_batch=200,
            retry_attempts=0,
            max_attempts=1,
        )
        assert len(df) == 3
        fetch_url = mock_get.call_args_list[-1].args[0]
        assert "start=0&" in fetch_url

    def test_start_id_carries_past_empty_windows(self):
        """A window with zero results does not consume start_id: there
        is nothing in it to skip, so the offset applies to the first
        window that actually has results."""
        records = [make_record(i) for i in range(2, 5)]
        responses = [
            fake_response(0, []),  # window 1: empty
            fake_response(5, []),  # window 2 count
            fake_response(3, records),  # window 2 fetch from index 2
        ]
        df, mock_get = self.run(
            responses,
            start_id=2,
            start_date="2020-01-01",
            end_date="2020-12-31",
            days_per_batch=200,
        )
        assert len(df) == 3
        fetch_url = mock_get.call_args_list[-1].args[0]
        assert "start=2&" in fetch_url

    def test_selected_fields_in_url(self):
        responses = [fake_response(1, []), fake_response(1, [make_record(0)])]
        _, mock_get = self.run(responses, fields=["itemid", "article"])
        url = mock_get.call_args_list[0].args[0]
        assert "select=itemid,article" in url

    def test_default_fields_include_placeholder_metadata(self):
        responses = [fake_response(1, []), fake_response(1, [make_record(0)])]
        _, mock_get = self.run(responses, fields=None)
        url = mock_get.call_args_list[0].args[0]
        selected = url.split("select=", 1)[1].split("&", 1)[0].split(",")
        assert "application" in selected
        assert "isplaceholder" in selected

    def test_over_10k_windows_are_partitioned_automatically(self):
        """Regression: HUDOC refuses to page past 10,000 results per
        query (start+length above the cap returns zero rows), so a
        count above 10k used to silently truncate at exactly 10,000."""
        big = [make_record(i) for i in range(8000)]
        small = [make_record(i) for i in range(8000, 12000)]
        responses = [
            fake_response(12000, []),  # whole window: over the cap -> split
            fake_response(8000, []),  # first half fits
            fake_response(8000, big),
            fake_response(4000, []),  # second half fits
            fake_response(4000, small),
        ]
        df, mock_get = self.run(responses, batch_size=8000)
        assert len(df) == 12000
        assert df["itemid"].is_unique
        # the split probes carry kpdate bounds
        assert "kpdate" in mock_get.call_args_list[1].args[0]

    def test_unsplittable_over_10k_query_warns_and_caps(self, caplog):
        records = [make_record(i) for i in range(10000)]
        responses = [
            fake_response(15000, []),
            fake_response(15000, records),
        ]
        link = hudoc_link('{"article":["6"]}')
        df, mock_get = self.run(responses, link=link, batch_size=10000)
        assert len(df) == 10000
        assert "at most 10000" in caplog.text
        # the fetch never pages past the cap
        assert "start=0&length=10000" in mock_get.call_args_list[1].args[0]

    def test_link_query_fetches_filtered_results(self):
        link = hudoc_link('{"article":["10"],"respondent":["NLD"]}')
        responses = [fake_response(1, []), fake_response(1, [make_record(0)])]
        df, mock_get = self.run(responses, link=link)
        url = mock_get.call_args_list[0].args[0]
        assert "article=%2210%22" in url
        assert "respondent=%22NLD%22" in url
        assert len(df) == 1
