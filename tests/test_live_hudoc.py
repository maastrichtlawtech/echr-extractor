"""Live integration tests against the real HUDOC API.

Skipped by default; enable with:

    pytest --run-live tests/test_live_hudoc.py
    # or
    ECHR_RUN_LIVE=1 pytest tests/test_live_hudoc.py

These tests keep result counts small where possible, but they do real
network requests and take minutes rather than seconds.
"""

import pandas as pd
import pytest

from echr_extractor import get_document_citations, get_echr, get_nodes_edges

pytestmark = pytest.mark.live

FIELDS = [
    "itemid",
    "docname",
    "kpdate",
    "languageisocode",
    "article",
    "respondent",
    "documentcollectionid2",
]

EDGE_FIELDS = [
    "itemid",
    "appno",
    "article",
    "conclusion",
    "docname",
    "doctype",
    "doctypebranch",
    "ecli",
    "importance",
    "judgementdate",
    "languageisocode",
    "originatingbody",
    "violation",
    "nonviolation",
    "extractedappno",
    "scl",
]


def fetch(**kwargs):
    defaults = dict(save_file="n", progress_bar=False, verbose=False)
    defaults.update(kwargs)
    return get_echr(**defaults)


def trace_references(df, edges):
    """Count how many edge references are supported by the citing scl."""

    def ident(row):
        ecli = row["ecli"]
        if pd.notna(ecli) and str(ecli).strip():
            return str(ecli).strip()
        return str(row["itemid"]).strip()

    lookup = df.assign(_id=df.apply(ident, axis=1)).set_index("_id", drop=False)
    lookup = lookup[~lookup.index.duplicated(keep="first")]
    traced = total = 0
    for _, edge in edges.iterrows():
        citing = lookup.loc[[edge["ecli"]]].iloc[0]
        scl = str(citing["scl"]).upper()
        for ref_id in edge["references"]:
            total += 1
            cited = lookup.loc[[ref_id]].iloc[0]
            appnos = [
                a.strip() for a in str(cited["appno"]).split(";") if a.strip()
            ]
            surname = (
                str(cited["docname"])
                .upper()
                .replace("CASE OF ", "")
                .replace("AFFAIRE ", "")
                .split(" V.")[0]
                .split(" C.")[0]
                .strip()
            )
            if any(a in scl for a in appnos) or (
                len(surname) > 3 and surname in scl
            ):
                traced += 1
    return traced, total


class TestLiveFilters:
    def test_baseline_fetch(self):
        df = fetch(count=10, fields=FIELDS)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 10
        assert df["itemid"].notna().all()

    def test_date_filter_bounds_are_respected(self):
        df = fetch(
            count=50,
            start_date="2023-01-01",
            end_date="2023-06-30",
            fields=FIELDS,
        )
        assert len(df) > 0
        dates = pd.to_datetime(df["kpdate"])
        assert (dates >= "2023-01-01").all()
        assert (dates <= "2023-06-30 23:59:59").all()

    def test_single_day_date_range(self):
        """Regression: single-day ranges used to produce zero batches."""
        # 2023-01-24 is a Tuesday with published judgments
        df = fetch(count=20, start_date="2023-01-24", end_date="2023-01-24")
        assert df is not False
        assert len(df) > 0

    def test_language_filter(self):
        df = fetch(count=30, language=["FRE"], fields=FIELDS)
        assert len(df) > 0
        assert (df["languageisocode"] == "FRE").all()

    def test_multiple_languages(self):
        df = fetch(count=100, language=["ENG", "FRE"], fields=FIELDS)
        assert set(df["languageisocode"].unique()) <= {"ENG", "FRE"}

    def test_link_with_article_and_respondent_filters(self):
        """Regression: unmapped link keys were silently dropped, so this
        used to return the entire database instead of ~60 cases."""
        link = (
            "https://hudoc.echr.coe.int/eng#"
            '{%22article%22:[%2210%22],%22respondent%22:[%22NLD%22],'
            "%22documentcollectionid2%22:[%22JUDGMENTS%22]}"
        )
        df = fetch(link=link, fields=FIELDS)
        assert df is not False
        # Article 10 v. Netherlands judgments: a small, stable set
        assert len(df) < 500
        assert df["article"].str.split(";").apply(lambda a: "10" in a).all()
        assert (df["respondent"].str.split(";").apply(lambda r: "NLD" in r)).all()

    def test_link_with_docname_and_kpdate(self):
        link = (
            "https://hudoc.echr.coe.int/eng#"
            '{%22docname%22:[%22turkey%22],'
            "%22kpdate%22:[%222020-01-01%22,%222020-12-31%22]}"
        )
        df = fetch(count=50, link=link, fields=FIELDS)
        assert len(df) > 0
        assert df["docname"].str.contains("turkey", case=False).all()
        dates = pd.to_datetime(df["kpdate"])
        assert (dates.dt.year == 2020).all()

    def test_link_with_itemid(self):
        link = (
            "https://hudoc.echr.coe.int/eng#"
            "{%22itemid%22:[%22001-100448%22]}"
        )
        df = fetch(link=link, fields=FIELDS)
        assert len(df) == 1
        assert df.iloc[0]["itemid"] == "001-100448"

    def test_query_payload(self):
        payload = (
            "(contentsitename=ECHR)%20AND%20"
            "(documentcollectionid2:%22JUDGMENTS%22)"
        )
        df = fetch(count=10, query_payload=payload, fields=FIELDS)
        assert len(df) == 10
        assert (
            df["documentcollectionid2"]
            .str.contains("JUDGMENTS", case=False)
            .all()
        )


class TestLiveLargeFetch:
    def test_fetch_beyond_hudoc_10k_pagination_cap(self):
        """Regression: HUDOC caps pagination at 10,000 rows per query;
        count=15000 used to silently return exactly 10,000. The query
        must be partitioned into date windows automatically."""
        df = fetch(count=10500, language=["ENG"], fields=["itemid", "kpdate"])
        assert len(df) == 10500
        assert df["itemid"].is_unique


class TestLiveReferenceResolution:
    def test_single_document_out_citations(self):
        """Sanoma Uitgevers B.V. v. the Netherlands [GC] cites ~20 cases;
        the resolver must find most of them in HUDOC."""
        result = get_document_citations(itemid="001-100448")
        assert len(result) > 10
        resolved = result[result["resolved_id"].notna()]
        assert len(resolved) / len(result) > 0.6
        # appno-resolved targets must carry the appno cited in the text
        for _, row in resolved[resolved["match_method"] == "appno"].iterrows():
            assert any(
                a in row["missing_references"]
                for a in row["extracted_appnos"].split(";")
            )
        # a famous known citation must be among them
        assert (
            resolved["resolved_docname"]
            .str.contains("GOODWIN", case=False)
            .any()
        )

    def test_network_with_external_resolution(self):
        df = fetch(
            start_date="2022-01-10",
            end_date="2022-01-20",
            fields=EDGE_FIELDS,
        )
        plain_nodes, plain_edges, plain_missing = get_nodes_edges(
            df=df, save_file="n"
        )
        nodes, edges, missing = get_nodes_edges(
            df=df, save_file="n", resolve_external=True
        )
        # resolution strictly reduces the unresolved set and adds nodes
        assert len(missing) < len(plain_missing)
        assert "in_corpus" in nodes.columns
        external = nodes[~nodes["in_corpus"]]
        assert len(external) > 0
        assert len(nodes) == len(plain_nodes) + len(external)
        # every edge target is now a known node identifier
        known = set(
            nodes.apply(
                lambda r: str(r.get("ecli")).strip()
                if pd.notna(r.get("ecli")) and str(r.get("ecli")).strip()
                else str(r.get("itemid")),
                axis=1,
            )
        )
        for refs in edges["references"]:
            assert set(refs) <= known


class TestLiveCitationNetwork:
    def test_small_network(self):
        """~3 months of judgments: the network must resolve real citations."""
        df = fetch(
            start_date="2022-01-01",
            end_date="2022-03-31",
            fields=EDGE_FIELDS,
        )
        assert df is not False and len(df) > 100

        nodes, edges, missing = get_nodes_edges(df=df, save_file="n")

        assert len(nodes) == len(df)
        assert len(edges) > 0
        # Every resolved reference must be a non-empty identifier (ECLI,
        # or itemid for documents without one) present in the corpus;
        # empty-string ECLIs used to leak in as phantom nodes
        known_ids = (set(df["ecli"].dropna()) | set(df["itemid"].dropna())) - {""}
        for refs in edges["references"]:
            assert "" not in refs
            assert set(refs) <= known_ids
        # Semantic check: references must trace back to the citing
        # case's scl text (by application number or case surname).
        # Guards against over-linking regressions (extractedappno
        # blending, substring matches on short docnames).
        traced, total = trace_references(df, edges)
        assert total > 0
        assert traced / total > 0.9, f"only {traced}/{total} references traced"

    def test_large_network(self):
        """Two years of judgments (~several thousand cases)."""
        df = fetch(
            start_date="2019-01-01",
            end_date="2020-12-31",
            fields=EDGE_FIELDS,
        )
        assert df is not False and len(df) > 2000

        nodes, edges, missing = get_nodes_edges(df=df, save_file="n")

        assert len(nodes) == len(df)
        assert len(edges) > 20
        known_ids = (set(df["ecli"].dropna()) | set(df["itemid"].dropna())) - {""}
        for refs in edges["references"]:
            assert "" not in refs
            assert set(refs) <= known_ids
        # Edges are aggregated: one row per citing ECLI
        assert edges["ecli"].is_unique
        traced, total = trace_references(df, edges)
        assert traced / total > 0.9, f"only {traced}/{total} references traced"
