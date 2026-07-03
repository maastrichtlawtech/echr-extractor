"""Unit tests for the citation network (nodes/edges) extraction.

These run on synthetic metadata so they are fast and deterministic.
Live end-to-end network construction is covered in test_live_hudoc.py.
"""

import pandas as pd

from echr_extractor.ECHR_nodes_edges_list_transform import (
    echr_nodes_edges,
    get_casename,
    get_year_from_ref,
    retrieve_edges_list,
)


def make_case(
    itemid,
    ecli,
    docname,
    appno="",
    lang="ENG",
    jdate="01/01/2000",
    scl=None,
    extractedappno=None,
):
    return {
        "itemid": itemid,
        "appno": appno,
        "docname": docname,
        "ecli": ecli,
        "languageisocode": lang,
        "judgementdate": jdate,
        "scl": scl,
        "extractedappno": extractedappno,
    }


HENTRICH = make_case(
    "001-1",
    "ECLI:CE:ECHR:1994:HENTRICH",
    "CASE OF HENTRICH v. FRANCE",
    appno="13616/88",
    jdate="22/09/1994",
)


def edges_for(cases):
    df = pd.DataFrame(cases)
    edges, missing = retrieve_edges_list(df, df)
    return edges, missing


class TestEdgeResolution:
    def test_reference_by_application_number(self):
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Hentrich v. France, no. 13616/88, 22 September 1994, § 42",
        )
        edges, missing = edges_for([HENTRICH, citing])

        assert len(edges) == 1
        assert edges.iloc[0]["ecli"] == "ECLI:CITING"
        assert edges.iloc[0]["references"] == ["ECLI:CE:ECHR:1994:HENTRICH"]
        assert len(missing) == 0

    def test_reference_by_case_name(self):
        """Regression: docname lookup must be case-consistent.

        The docname index keys are fully uppercased; the lookup text used
        to re-lowercase "V." so name-based references never resolved and
        all ended up in missing_references.
        """
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Hentrich v. France, 22 September 1994, § 42, Series A no. 296-A",
        )
        edges, missing = edges_for([HENTRICH, citing])

        assert len(edges) == 1
        assert edges.iloc[0]["references"] == ["ECLI:CE:ECHR:1994:HENTRICH"]
        assert len(missing) == 0

    def test_french_reference_by_case_name(self):
        cited = make_case(
            "001-1",
            "ECLI:CITED:FRE",
            "AFFAIRE HENTRICH c. FRANCE",
            appno="13616/88",
            lang="FRE",
            jdate="22/09/1994",
        )
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "AFFAIRE BBB c. BELGIQUE",
            appno="100/95",
            lang="FRE",
            scl="Hentrich c. France, 22 septembre 1994, § 42",
        )
        edges, missing = edges_for([cited, citing])

        assert len(edges) == 1
        assert edges.iloc[0]["references"] == ["ECLI:CITED:FRE"]

    def test_year_mismatch_is_rejected(self):
        wrong_year = dict(HENTRICH, jdate="22/09/1980", judgementdate="22/09/1980")
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Hentrich v. France, 22 September 1994, § 42",
        )
        edges, missing = edges_for([wrong_year, citing])

        assert len(edges) == 0
        assert "Hentrich v. France, 22 September 1994, § 42" in list(
            missing["missing_references"]
        )

    def test_language_mismatch_is_rejected(self):
        french_only = dict(HENTRICH, languageisocode="FRE")
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            # "v." in the reference implies an English-language citation
            scl="Hentrich v. France, no. 13616/88, 22 September 1994",
        )
        edges, _ = edges_for([french_only, citing])

        assert len(edges) == 0

    def test_multiple_references_aggregated_per_case(self):
        cited_two = make_case(
            "001-3",
            "ECLI:CITED:2",
            "CASE OF JAMES AND OTHERS v. THE UNITED KINGDOM",
            appno="8793/79",
            jdate="21/02/1986",
        )
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl=(
                "Hentrich v. France, no. 13616/88, 22 September 1994;"
                "James and Others v. the United Kingdom, no. 8793/79, "
                "21 February 1986"
            ),
        )
        edges, _ = edges_for([HENTRICH, cited_two, citing])

        assert len(edges) == 1
        assert sorted(edges.iloc[0]["references"]) == [
            "ECLI:CE:ECHR:1994:HENTRICH",
            "ECLI:CITED:2",
        ]

    def test_short_docname_requires_word_boundary(self):
        """Regression: 'A v. POLAND' must not match every reference whose
        casename merely ends in '...a v. Poland' (e.g. Bojara v. Poland)."""
        short_name = make_case(
            "001-7",
            "ECLI:SHORT",
            "A v. POLAND",
            appno="47023/16",
            jdate="01/06/2021",
        )
        real_cited = make_case(
            "001-8",
            "ECLI:BOJARA",
            "CASE OF BRODA AND BOJARA v. POLAND",
            appno="26691/18",
            jdate="29/06/2021",
        )
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Broda and Bojara v. Poland, 29 June 2021",
        )
        edges, _ = edges_for([short_name, real_cited, citing])

        assert len(edges) == 1
        assert edges.iloc[0]["references"] == ["ECLI:BOJARA"]

    def test_no_scl_produces_no_edges(self):
        edges, missing = edges_for([HENTRICH])
        assert len(edges) == 0
        assert list(edges.columns) == ["ecli", "references"]
        assert len(missing) == 0

    def test_empty_ecli_falls_back_to_itemid(self):
        """Regression: cases with an empty-string ECLI (communicated
        cases, CLIN notes) used to collapse into phantom '' nodes. They
        must instead be identified by their HUDOC itemid so their
        citations are preserved."""
        no_ecli_cited = dict(HENTRICH, ecli="")
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Hentrich v. France, no. 13616/88, 22 September 1994",
        )
        no_ecli_citing = dict(citing, ecli="", itemid="001-3", appno="200/95")
        edges, _ = edges_for([no_ecli_cited, citing, no_ecli_citing])

        assert "" not in set(edges["ecli"])
        for refs in edges["references"]:
            assert "" not in refs
        # The citing case without ECLI is keyed by its itemid
        assert set(edges["ecli"]) == {"ECLI:CITING", "001-3"}
        # The cited case without ECLI is referenced by its itemid
        for refs in edges["references"]:
            assert refs == ["001-1"]

    def test_no_identifier_at_all_is_dropped(self):
        citing = make_case(
            "",
            "",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Hentrich v. France, no. 13616/88, 22 September 1994",
        )
        edges, _ = edges_for([HENTRICH, citing])
        assert len(edges) == 0

    def test_unresolvable_reference_is_reported_missing(self):
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Nonexistent v. Nowhere, no. 99999/99, 1 January 1999",
        )
        edges, missing = edges_for([HENTRICH, citing])

        assert len(edges) == 0
        assert len(missing) == 1

    def test_self_reference_is_excluded(self):
        """A case must never appear in its own references (original
        behavior lost in the batching rewrite)."""
        case = make_case(
            "001-1",
            "ECLI:SELF",
            "CASE OF SELF v. SELF",
            appno="1/90",
            jdate="01/01/1990",
            scl="Self v. Self, no. 1/90, 1 January 1990",
        )
        edges, _ = edges_for([case])
        assert len(edges) == 0

    def test_document_level_extractedappno_not_blended_into_references(self):
        """Regression: each scl reference must resolve from its own text.
        Blending the citing document's extractedappno (every appno
        mentioned anywhere in its full text) linked each citation to
        every mentioned case."""
        unrelated = make_case(
            "001-9",
            "ECLI:UNRELATED",
            "CASE OF UNRELATED v. SPAIN",
            appno="777/90",
            jdate="05/05/1994",
        )
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Hentrich v. France, no. 13616/88, 22 September 1994",
            # mentions the unrelated case somewhere in its full text
            extractedappno="777/90;13616/88",
        )
        edges, _ = edges_for([HENTRICH, unrelated, citing])

        assert len(edges) == 1
        assert edges.iloc[0]["references"] == ["ECLI:CE:ECHR:1994:HENTRICH"]

    def test_reference_appno_does_not_match_co_citing_documents(self):
        """A reference 'no. 13616/88' identifies the case with that
        application number — not other documents whose extractedappno
        merely mentions it."""
        co_citing = make_case(
            "001-8",
            "ECLI:COCITING",
            "CASE OF OTHER v. ITALY",
            appno="500/90",
            jdate="22/09/1994",  # same year so the year filter cannot save us
            extractedappno="13616/88",
        )
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Hentrich v. France, no. 13616/88, 22 September 1994",
        )
        edges, _ = edges_for([HENTRICH, co_citing, citing])

        assert len(edges) == 1
        assert edges.iloc[0]["references"] == ["ECLI:CE:ECHR:1994:HENTRICH"]


class TestEchrNodesEdges:
    def test_with_dataframe(self):
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Hentrich v. France, no. 13616/88, 22 September 1994",
        )
        df = pd.DataFrame([HENTRICH, citing])
        nodes, edges, missing = echr_nodes_edges(data=df)

        assert len(nodes) == 2
        assert len(edges) == 1
        assert len(missing) == 0

    def test_with_metadata_path(self, tmp_path):
        citing = make_case(
            "001-2",
            "ECLI:CITING",
            "CASE OF AAA v. BELGIUM",
            appno="100/95",
            scl="Hentrich v. France, no. 13616/88, 22 September 1994",
        )
        path = tmp_path / "metadata.csv"
        pd.DataFrame([HENTRICH, citing]).to_csv(path, index=False)

        nodes, edges, missing = echr_nodes_edges(metadata_path=str(path))

        assert len(nodes) == 2
        assert len(edges) == 1

    def test_without_input_returns_empty(self):
        nodes, edges, missing = echr_nodes_edges()
        assert nodes == "" and edges == "" and missing == ""


class TestLargeSyntheticNetwork:
    def test_thousand_case_citation_chain(self):
        """Network construction should scale and stay correct on a larger
        corpus: 1000 cases where each case cites the previous one."""
        cases = []
        for i in range(1000):
            scl = None
            if i > 0:
                scl = f"Case{i - 1:04d} v. France, no. {1000 + i - 1}/90, 1 January 2000"
            cases.append(
                make_case(
                    f"001-{i}",
                    f"ECLI:{i:04d}",
                    f"CASE OF CASE{i:04d} v. FRANCE",
                    appno=f"{1000 + i}/90",
                    jdate="01/01/2000",
                    scl=scl,
                )
            )
        edges, missing = edges_for(cases)

        assert len(edges) == 999
        assert len(missing) == 0
        # Spot-check a link in the middle of the chain
        row = edges[edges["ecli"] == "ECLI:0500"].iloc[0]
        assert row["references"] == ["ECLI:0499"]


class TestHelpers:
    def test_get_casename_english(self):
        assert (
            get_casename("Hentrich v. France, 22 September 1994, § 42")
            == "Hentrich v. France"
        )

    def test_get_casename_french(self):
        assert (
            get_casename("Hentrich c. France, 22 septembre 1994")
            == "Hentrich c. France"
        )

    def test_get_casename_comma_in_name(self):
        assert (
            get_casename("Federation X, Union Y v. Belgium, 1 January 2000")
            == "Federation X, Union Y v. Belgium"
        )

    def test_get_year_from_ref(self):
        assert get_year_from_ref(["Hentrich v. France", " 22 September 1994"]) == 1994

    def test_get_year_from_ref_no_date(self):
        assert get_year_from_ref(["Hentrich v. France"]) == 0

    def test_get_year_from_ref_echr_citation(self):
        assert get_year_from_ref(["Foo v. Bar", " ECHR 2003-IV"]) == 2003
