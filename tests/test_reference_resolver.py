"""Unit tests for citation reference resolution (offline and mocked online)."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from echr_extractor import (
    get_document_citations,
    get_nodes_edges,
    parse_scl_references,
    resolve_references,
)
from echr_extractor.ECHR_nodes_edges_list_transform import (
    MISSING_REFERENCE_COLUMNS,
    retrieve_edges_list,
)

HENTRICH_ROW = {
    "itemid": "001-57903",
    "appno": "13616/88",
    "docname": "CASE OF HENTRICH v. FRANCE",
    "ecli": "ECLI:CE:ECHR:1994:HENTRICH",
    "languageisocode": "ENG",
    "judgementdate": "22/09/1994",
    "kpdate": "1994-09-22T00:00:00",
    "doctype": "HEJUD",
    "doctypebranch": "CHAMBER",
    "documentcollectionid2": "CASELAW;JUDGMENTS;CHAMBER;ENG",
}

SCL = (
    "Hentrich v. France, no. 13616/88, 22 September 1994, § 42;"
    "Unknown v. Nowhere, no. 99999/99, 1 January 1999"
)


class TestParseSclReferences:
    def test_one_row_per_reference_with_parsed_fields(self):
        refs = parse_scl_references(SCL, citing_id="ECLI:CITING")
        assert list(refs.columns) == MISSING_REFERENCE_COLUMNS
        assert len(refs) == 2
        first = refs.iloc[0]
        assert first["citing_id"] == "ECLI:CITING"
        assert first["extracted_appnos"] == "13616/88"
        assert first["casename"] == "Hentrich v. France"
        assert first["year"] == 1994
        assert first["ref_language"] == "ENG"

    def test_french_reference_language(self):
        refs = parse_scl_references("Hentrich c. France, 22 septembre 1994")
        assert refs.iloc[0]["ref_language"] == "FRE"

    def test_empty_and_nan_scl(self):
        assert len(parse_scl_references(None)) == 0
        assert len(parse_scl_references(float("nan"))) == 0
        assert len(parse_scl_references("")) == 0

    def test_parse_matches_network_builder_missing_table(self):
        """Drift guard: parse_scl_references and the network builder's
        missing-references table are built from the same shared helpers
        and must stay row-for-row identical."""
        scl = (
            "Nonexistent v. Nowhere, no. 99999/99, 1 January 1999;"
            "Eur. Court H.R. Ghost v. Void judgment of 27 October 1975"
        )
        citing = pd.DataFrame(
            [
                {
                    "itemid": "001-2",
                    "appno": "100/95",
                    "docname": "CASE OF AAA v. BELGIUM",
                    "ecli": "ECLI:CITING",
                    "languageisocode": "ENG",
                    "judgementdate": "01/01/2000",
                    "extractedappno": None,
                    "scl": scl,
                }
            ]
        )
        _, missing = retrieve_edges_list(citing, citing)
        refs = parse_scl_references(scl, citing_id="ECLI:CITING")
        pd.testing.assert_frame_equal(refs, missing)


class TestResolveOffline:
    def reference_df(self, extra_rows=()):
        return pd.DataFrame([HENTRICH_ROW, *extra_rows])

    def missing(self, **overrides):
        row = {
            "citing_id": "ECLI:CITING",
            "missing_references": "Hentrich v. France, no. 13616/88, 22 September 1994",
            "extracted_appnos": "13616/88",
            "casename": "Hentrich v. France",
            "year": 1994,
            "ref_language": "ENG",
        }
        row.update(overrides)
        return pd.DataFrame([row])

    def test_resolves_by_appno(self):
        resolved, external, still = resolve_references(
            self.missing(), reference_df=self.reference_df()
        )
        assert len(resolved) == 1
        assert resolved.iloc[0]["resolved_id"] == "ECLI:CE:ECHR:1994:HENTRICH"
        assert resolved.iloc[0]["match_method"] == "appno"
        assert list(external["itemid"]) == ["001-57903"]
        assert len(still) == 0

    def test_resolves_by_casename_when_no_appno(self):
        resolved, _, still = resolve_references(
            self.missing(
                extracted_appnos="",
                missing_references="Hentrich v. France, 22 September 1994",
            ),
            reference_df=self.reference_df(),
        )
        assert len(resolved) == 1
        assert resolved.iloc[0]["match_method"] == "casename"

    def test_year_mismatch_stays_unresolved(self):
        resolved, _, still = resolve_references(
            self.missing(year=1980), reference_df=self.reference_df()
        )
        assert len(resolved) == 0
        assert len(still) == 1
        assert still.iloc[0]["missing_references"].startswith("Hentrich")

    def test_language_mismatch_stays_unresolved(self):
        resolved, _, still = resolve_references(
            self.missing(ref_language="FRE"), reference_df=self.reference_df()
        )
        assert len(resolved) == 0 and len(still) == 1

    def test_judgment_preferred_over_other_doctypes(self):
        clin = dict(
            HENTRICH_ROW,
            itemid="002-9999",
            ecli="",
            doctype="CLIN",
            documentcollectionid2="CASELAW;CLIN;ENG",
        )
        resolved, _, _ = resolve_references(
            self.missing(), reference_df=self.reference_df([clin])
        )
        assert resolved.iloc[0]["resolved_itemid"] == "001-57903"
        assert resolved.iloc[0]["candidate_count"] == 2

    def test_failed_appno_falls_back_to_casename(self):
        """A mistyped application number must not prevent resolution when
        the casename identifies the document (network-builder parity)."""
        resolved, _, _ = resolve_references(
            self.missing(
                extracted_appnos="99999/99",
                missing_references="Hentrich v. France, no. 99999/99, 22 September 1994",
            ),
            reference_df=self.reference_df(),
        )
        assert len(resolved) == 1
        assert resolved.iloc[0]["match_method"] == "casename"

    def test_never_resolves_to_the_citing_document(self):
        resolved, _, still = resolve_references(
            self.missing(citing_id="ECLI:CE:ECHR:1994:HENTRICH"),
            reference_df=self.reference_df(),
        )
        assert len(resolved) == 0 and len(still) == 1

    def test_old_style_citation_resolves_by_casename(self):
        """Regression: old-style citations carry 'Eur. Court H.R.' and
        'judgment of <date>' boilerplate. The resolver used to skip the
        clean_pattern regexes the network builder applies, so the
        docname lookup never matched and these stayed unresolved."""
        refs = parse_scl_references(
            "Eur. Court H.R. Hentrich v. France judgment of "
            "22 September 1994, Series A no. 296-A",
            citing_id="ECLI:CITING",
        )
        resolved, _, still = resolve_references(
            refs, reference_df=self.reference_df()
        )
        assert len(still) == 0
        assert len(resolved) == 1
        assert resolved.iloc[0]["resolved_id"] == "ECLI:CE:ECHR:1994:HENTRICH"
        assert resolved.iloc[0]["match_method"] == "casename"

    def test_old_style_citation_with_comma_after_reporter(self):
        """The 'Eur. Court H.R., <name> judgment of <date>' variant
        leaves a leading comma behind after boilerplate stripping; it
        must be trimmed for the docname lookup to match."""
        refs = parse_scl_references(
            "Eur. Court H.R., Hentrich v. France judgment of "
            "22 September 1994, Series A no. 296-A",
            citing_id="ECLI:CITING",
        )
        resolved, _, still = resolve_references(
            refs, reference_df=self.reference_df()
        )
        assert len(still) == 0
        assert resolved.iloc[0]["resolved_id"] == "ECLI:CE:ECHR:1994:HENTRICH"

    def test_old_style_citation_without_respondent_resolves(self):
        """Regression: old-style citations that omit the respondent
        ('Eur. Court H.R. James and Others judgment of ...') contain no
        'v.' marker and were misclassified as French, so the language
        filter rejected the English target even after normalization."""
        belgian_police = dict(
            HENTRICH_ROW,
            itemid="001-57435",
            appno="4464/70",
            docname="CASE OF NATIONAL UNION OF BELGIAN POLICE v. BELGIUM",
            ecli="ECLI:CE:ECHR:1975:BELPOLICE",
            judgementdate="27/10/1975",
            kpdate="1975-10-27T00:00:00",
        )
        refs = parse_scl_references(
            "Eur. Court H.R. National Union of Belgian Police judgment "
            "of 27 October 1975, Series A no. 19",
            citing_id="ECLI:CITING",
        )
        assert refs.iloc[0]["ref_language"] == ""
        resolved, _, still = resolve_references(
            refs, reference_df=pd.DataFrame([belgian_police])
        )
        assert len(still) == 0
        assert resolved.iloc[0]["resolved_id"] == "ECLI:CE:ECHR:1975:BELPOLICE"

    def test_online_docname_query_uses_normalized_casename(self):
        """Regression: the online candidate fetch queried HUDOC with the
        raw casename including 'judgment of' boilerplate, so old-style
        targets never entered the candidate pool."""
        refs = parse_scl_references(
            "Eur. Court H.R. National Union of Belgian Police judgment "
            "of 27 October 1975, Series A no. 19",
            citing_id="ECLI:CITING",
        )
        with patch(
            "echr_extractor.ECHR_metadata_harvester.requests.get",
            return_value=hudoc_response([]),
        ) as mock_get:
            resolve_references(refs)
        url = mock_get.call_args_list[0].args[0]
        assert "NATIONAL%20UNION%20OF%20BELGIAN%20POLICE" in url
        assert "JUDGMENT%20OF" not in url

    def test_original_document_preferred_over_translation(self):
        """When the reference language is unknown, the original ENG/FRE
        judgment must outrank translation entries (which would otherwise
        win on itemid order)."""
        translation = dict(
            HENTRICH_ROW,
            itemid="001-00001",  # sorts before the original
            ecli="ECLI:TRANSLATION",
            docname="CASE OF HENTRICH v. FRANCE - [Russian Translation]",
            languageisocode="RUS",
        )
        refs = parse_scl_references(
            "Eur. Court H.R. Hentrich judgment of 22 September 1994",
            citing_id="ECLI:CITING",
        )
        assert refs.iloc[0]["ref_language"] == ""
        resolved, _, still = resolve_references(
            refs, reference_df=pd.DataFrame([translation, HENTRICH_ROW])
        )
        assert len(still) == 0
        assert resolved.iloc[0]["resolved_id"] == "ECLI:CE:ECHR:1994:HENTRICH"

    def test_nan_itemid_rows_are_ignored(self):
        """Regression: reference_df rows with NaN itemids used to
        stringify to 'nan' and become phantom external nodes."""
        nan_itemid = dict(HENTRICH_ROW, itemid=float("nan"), ecli="ECLI:NAN")
        resolved, external, still = resolve_references(
            self.missing(), reference_df=pd.DataFrame([nan_itemid])
        )
        assert len(resolved) == 0 and len(still) == 1
        assert len(external) == 0

    def test_missing_required_columns_raises(self):
        malformed = pd.DataFrame(
            [{"citing_id": "ECLI:CITING", "missing_references": "X v. Y"}]
        )
        with pytest.raises(ValueError, match="parse_scl_references"):
            resolve_references(malformed, reference_df=self.reference_df())

    def test_empty_missing_df(self):
        resolved, external, still = resolve_references(
            pd.DataFrame(columns=MISSING_REFERENCE_COLUMNS)
        )
        assert len(resolved) == 0 and len(external) == 0 and len(still) == 0


def hudoc_response(rows):
    response = MagicMock()
    response.json.return_value = {
        "resultcount": len(rows),
        "results": [{"columns": r} for r in rows],
    }
    response.raise_for_status.return_value = None
    return response


class TestResolveOnline:
    def test_batched_appno_query_resolves(self):
        missing = pd.DataFrame(
            [
                {
                    "citing_id": "ECLI:CITING",
                    "missing_references": (
                        "Hentrich v. France, no. 13616/88, 22 September 1994"
                    ),
                    "extracted_appnos": "13616/88",
                    "casename": "Hentrich v. France",
                    "year": 1994,
                    "ref_language": "ENG",
                }
            ]
        )
        with patch(
            "echr_extractor.ECHR_metadata_harvester.requests.get",
            return_value=hudoc_response([HENTRICH_ROW]),
        ) as mock_get:
            resolved, external, still = resolve_references(missing)

        assert len(resolved) == 1
        assert resolved.iloc[0]["resolved_id"] == "ECLI:CE:ECHR:1994:HENTRICH"
        url = mock_get.call_args_list[0].args[0]
        assert "appno" in url and "13616/88" in url
        # press releases are excluded from candidate queries
        assert "NOT%20(doctype=PR" in url

    def test_second_pass_fetches_docname_candidates_for_failed_appnos(self):
        """When an appno matches nothing in HUDOC, a second query round
        must look the reference up by casename."""
        missing = pd.DataFrame(
            [
                {
                    "citing_id": "ECLI:CITING",
                    "missing_references": (
                        "Hentrich v. France, no. 99999/99, 22 September 1994"
                    ),
                    "extracted_appnos": "99999/99",
                    "casename": "Hentrich v. France",
                    "year": 1994,
                    "ref_language": "ENG",
                }
            ]
        )
        responses = [
            hudoc_response([]),              # appno query: nothing
            hudoc_response([HENTRICH_ROW]),  # docname retry: found
        ]
        with patch(
            "echr_extractor.ECHR_metadata_harvester.requests.get",
            side_effect=responses,
        ) as mock_get:
            resolved, _, still = resolve_references(missing)

        assert len(resolved) == 1
        assert resolved.iloc[0]["match_method"] == "casename"
        assert len(still) == 0
        retry_url = mock_get.call_args_list[1].args[0]
        assert "docname" in retry_url


class TestGetNodesEdgesResolution:
    def corpus(self):
        citing = {
            "itemid": "001-2",
            "appno": "100/95",
            "docname": "CASE OF AAA v. BELGIUM",
            "ecli": "ECLI:CITING",
            "languageisocode": "ENG",
            "judgementdate": "01/01/2000",
            "extractedappno": None,
            "scl": "Hentrich v. France, no. 13616/88, 22 September 1994",
        }
        return pd.DataFrame([citing])

    def test_reference_df_resolution_adds_external_edges_and_nodes(self):
        nodes, edges, missing = get_nodes_edges(
            df=self.corpus(),
            save_file="n",
            reference_df=pd.DataFrame([HENTRICH_ROW]),
        )
        assert len(missing) == 0
        assert len(edges) == 1
        assert edges.iloc[0]["ecli"] == "ECLI:CITING"
        assert edges.iloc[0]["references"] == ["ECLI:CE:ECHR:1994:HENTRICH"]
        assert "in_corpus" in nodes.columns
        assert len(nodes) == 2
        external = nodes[~nodes["in_corpus"]]
        assert list(external["itemid"]) == ["001-57903"]

    def test_without_resolution_shape_is_unchanged(self):
        nodes, edges, missing = get_nodes_edges(df=self.corpus(), save_file="n")
        assert "in_corpus" not in nodes.columns
        assert len(edges) == 0
        assert len(missing) == 1
        assert missing.iloc[0]["extracted_appnos"] == "13616/88"


class TestGetDocumentCitations:
    def test_in_memory_document_without_resolution(self):
        result = get_document_citations(
            document={"itemid": "001-2", "ecli": "ECLI:X", "scl": SCL},
            resolve=False,
        )
        assert len(result) == 2
        assert result.iloc[0]["citing_id"] == "ECLI:X"

    def test_in_memory_document_with_offline_resolution(self):
        result = get_document_citations(
            document={"itemid": "001-2", "ecli": "ECLI:X", "scl": SCL},
            reference_df=pd.DataFrame([HENTRICH_ROW]),
        )
        assert len(result) == 2
        resolved = result[result["resolved_id"].notna()]
        assert len(resolved) == 1
        assert resolved.iloc[0]["resolved_docname"] == "CASE OF HENTRICH v. FRANCE"
        unresolved = result[result["resolved_id"].isna()]
        assert unresolved.iloc[0]["missing_references"].startswith("Unknown")

    def test_requires_itemid_or_document(self):
        with pytest.raises(ValueError):
            get_document_citations()
