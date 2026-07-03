"""Resolve citation references against HUDOC or an offline reference set.

The citation network built by echr_nodes_edges is self-enclosed: edges
only point at documents present in the corpus that was passed in.
References to cases outside that corpus are reported in the missing
references table (see MISSING_REFERENCE_COLUMNS). This module resolves
those references to real HUDOC documents, either:

- offline, against a larger metadata DataFrame (``reference_df``), or
- online, by querying HUDOC with batched application-number and
  casename queries (re-using the metadata scraper).

References that cannot be resolved are returned untouched, never
dropped.
"""

import logging
import re

import pandas as pd

from .ECHR_metadata_harvester import basic_function, get_r
from .ECHR_nodes_edges_list_transform import (
    MISSING_REFERENCE_COLUMNS,
    get_casename,
    get_year_from_ref,
    node_identifier,
    parse_date_cached,
)

RESOLVER_FIELDS = [
    "itemid",
    "appno",
    "docname",
    "ecli",
    "languageisocode",
    "judgementdate",
    "kpdate",
    "doctype",
    "doctypebranch",
    "documentcollectionid2",
]

RESOLVED_COLUMNS = MISSING_REFERENCE_COLUMNS + [
    "resolved_id",
    "resolved_itemid",
    "resolved_docname",
    "match_method",
    "candidate_count",
]

_APPNOS_PER_QUERY = 20
_CASENAMES_PER_QUERY = 10
_PAGE_LENGTH = 500


def parse_scl_references(scl, citing_id=None):
    """Parse an scl citation string into one row per reference.

    Returns a DataFrame with MISSING_REFERENCE_COLUMNS, the same shape
    as the missing-references table produced by the network builder.
    """
    rows = []
    if scl is None or (isinstance(scl, float) and pd.isna(scl)):
        return pd.DataFrame(columns=MISSING_REFERENCE_COLUMNS)
    for ref in str(scl).split(";"):
        ref = re.sub("\n", "", ref).strip()
        if not ref:
            continue
        appnos = [
            x.strip()
            for x in re.findall(r"[0-9]{3,5}\/[0-9]{2}", ref)
            if x.strip()
        ]
        components = ref.split(",")
        year = get_year_from_ref(components)
        rows.append(
            {
                "citing_id": citing_id,
                "missing_references": ref,
                "extracted_appnos": ";".join(appnos),
                "casename": str(get_casename(ref) or "").strip(),
                "year": year if year > 0 else None,
                "ref_language": "ENG" if "v." in components[0] else "FRE",
            }
        )
    if not rows:
        return pd.DataFrame(columns=MISSING_REFERENCE_COLUMNS)
    return pd.DataFrame(rows).drop_duplicates(
        subset=["citing_id", "missing_references"]
    ).reset_index(drop=True)


def _normalize_casename(casename):
    uptext = str(casename).upper()
    if "BV" in uptext:
        uptext = uptext.replace("BV", "B.V.")
    uptext = re.sub(r"\[.*", "", uptext)
    return uptext.strip()


def _fetch_candidates(query, timeout, retry_attempts, max_attempts, verbose):
    """Run one HUDOC query and return the result rows."""
    base = (
        "https://hudoc.echr.coe.int/app/query/results?query=contentsitename:ECHR"
        " AND (NOT (doctype=PR OR doctype=HFCOMOLD OR doctype=HECOMOLD)) AND "
        f"{query}&select={','.join(RESOLVER_FIELDS)}"
        "&sort=itemid Ascending&start={start}&length={length}"
    )
    base = base.replace(" ", "%20").replace('"', "%22")

    results = []
    start = 0
    while True:
        url = base.format(start=start, length=_PAGE_LENGTH)
        r = get_r(url, timeout, retry_attempts, verbose, max_attempts)
        if r is None:
            logging.warning("Reference resolution query failed; some "
                            "references may stay unresolved")
            break
        try:
            payload = r.json()
            page = [res["columns"] for res in payload["results"]]
        except (KeyError, ValueError) as e:
            logging.warning(f"Could not parse resolution response: {e}")
            break
        results.extend(page)
        start += _PAGE_LENGTH
        if start >= payload.get("resultcount", 0) or not page:
            break
    return results


def _candidate_pool_online(
    missing_df, timeout, retry_attempts, max_attempts, verbose
):
    """Fetch candidate documents from HUDOC for all unique references."""
    appnos = set()
    casenames = set()
    for _, row in missing_df.iterrows():
        row_appnos = [
            a.strip() for a in str(row["extracted_appnos"] or "").split(";")
            if a.strip()
        ]
        if row_appnos:
            appnos.update(row_appnos)
        elif str(row["casename"] or "").strip():
            casenames.add(str(row["casename"]).strip())

    candidates = []
    appno_list = sorted(appnos)
    for i in range(0, len(appno_list), _APPNOS_PER_QUERY):
        chunk = appno_list[i : i + _APPNOS_PER_QUERY]
        candidates.extend(
            _fetch_candidates(
                basic_function("appno", chunk),
                timeout, retry_attempts, max_attempts, verbose,
            )
        )
    casename_list = sorted(casenames)
    for i in range(0, len(casename_list), _CASENAMES_PER_QUERY):
        chunk = casename_list[i : i + _CASENAMES_PER_QUERY]
        candidates.extend(
            _fetch_candidates(
                basic_function("docname", chunk),
                timeout, retry_attempts, max_attempts, verbose,
            )
        )
    if not candidates:
        return pd.DataFrame(columns=RESOLVER_FIELDS)
    pool = pd.DataFrame(candidates)
    return pool.drop_duplicates(subset=["itemid"]).reset_index(drop=True)


def _index_pool(pool):
    appno_index, docname_index = {}, {}
    rows = []
    for _, row in pool.iterrows():
        ident = node_identifier(row.get("ecli"), row.get("itemid"))
        if not ident:
            continue
        year = None
        for date_col in ("judgementdate", "kpdate"):
            value = row.get(date_col)
            if pd.notna(value) and str(value).strip():
                date = parse_date_cached(str(value))
                if date:
                    year = date.year
                    break
        lang = (
            str(row.get("languageisocode")).upper()
            if pd.notna(row.get("languageisocode"))
            else ""
        )
        collection = (
            str(row.get("documentcollectionid2")).upper()
            if pd.notna(row.get("documentcollectionid2"))
            else ""
        )
        entry = {
            "ident": ident,
            "itemid": str(row.get("itemid") or ""),
            "docname": str(row.get("docname") or ""),
            "year": year,
            "lang": lang,
            "is_judgment": "JUDGMENTS" in collection
            or str(row.get("doctype") or "").startswith("HEJUD"),
        }
        rows.append(entry)
        pos = len(rows) - 1
        if pd.notna(row.get("appno")):
            for a in str(row["appno"]).split(";"):
                a = a.strip()
                if a:
                    appno_index.setdefault(a, []).append(pos)
        docname = str(row.get("docname") or "").strip().upper()
        if docname:
            docname_index.setdefault(docname, []).append(pos)
    return rows, appno_index, docname_index


def _filter_candidates(positions, entries, row):
    year = row["year"]
    ref_lang = str(row["ref_language"] or "")
    survivors = []
    for pos in positions:
        entry = entries[pos]
        if ref_lang and entry["lang"] and ref_lang not in entry["lang"]:
            continue
        if pd.notna(year) and year and entry["year"] and entry["year"] != int(year):
            continue
        survivors.append(entry)
    return survivors


def _match_reference(row, entries, appno_index, docname_index):
    """Pick the best candidate for one reference; None if none survive.

    Application numbers are tried first; like the network builder, the
    casename is used as a fallback when they match nothing.
    """
    appnos = [
        a.strip() for a in str(row["extracted_appnos"] or "").split(";")
        if a.strip()
    ]
    survivors, method = [], "none"
    if appnos:
        positions = set()
        for a in appnos:
            positions.update(appno_index.get(a, []))
        survivors = _filter_candidates(positions, entries, row)
        method = "appno"

    if not survivors:
        uptext = _normalize_casename(row["casename"])
        if not uptext:
            return None, method if appnos else "none", 0
        positions = set()
        if uptext in docname_index:
            positions.update(docname_index[uptext])
        else:
            padded_up = f" {uptext} "
            for docname, pos_list in docname_index.items():
                if padded_up in f" {docname} " or f" {docname} " in padded_up:
                    positions.update(pos_list)
        casename_survivors = _filter_candidates(positions, entries, row)
        if casename_survivors:
            survivors, method = casename_survivors, "casename"

    if not survivors:
        return None, method, 0
    # Deterministic best: prefer judgments, then stable itemid order
    survivors.sort(key=lambda e: (not e["is_judgment"], e["itemid"]))
    return survivors[0], method, len(survivors)


def _match_rows(rows_df, pool):
    """Match every reference row against the candidate pool."""
    entries, appno_index, docname_index = _index_pool(pool)
    resolved_rows, missing_rows = [], []
    resolved_itemids = set()
    for _, row in rows_df.iterrows():
        entry, method, n_candidates = _match_reference(
            row, entries, appno_index, docname_index
        )
        # A citation must never resolve to the citing document itself
        if entry is not None and entry["ident"] == row["citing_id"]:
            entry = None
        if entry is None:
            missing_rows.append(row)
            continue
        resolved = dict(row)
        resolved.update(
            {
                "resolved_id": entry["ident"],
                "resolved_itemid": entry["itemid"],
                "resolved_docname": entry["docname"],
                "match_method": method,
                "candidate_count": n_candidates,
            }
        )
        resolved_rows.append(resolved)
        resolved_itemids.add(entry["itemid"])
    return resolved_rows, missing_rows, resolved_itemids


def resolve_references(
    missing_df,
    reference_df=None,
    verbose=False,
    timeout=60,
    retry_attempts=3,
    max_attempts=20,
):
    """Resolve unresolved citation references to real HUDOC documents.

    :param pd.DataFrame missing_df: Missing-references table from
        get_nodes_edges() (or parse_scl_references()).
    :param pd.DataFrame reference_df: Optional metadata DataFrame to
        resolve against offline. When omitted, HUDOC is queried with
        batched application-number and casename lookups.
    :return: tuple (resolved_df, external_nodes_df, still_missing_df).
        resolved_df has RESOLVED_COLUMNS; external_nodes_df holds one
        metadata row per distinct resolved document; still_missing_df
        contains the rows that could not be resolved, unchanged.
    """
    if missing_df is None or len(missing_df) == 0:
        return (
            pd.DataFrame(columns=RESOLVED_COLUMNS),
            pd.DataFrame(columns=RESOLVER_FIELDS),
            pd.DataFrame(columns=MISSING_REFERENCE_COLUMNS),
        )

    if reference_df is not None:
        pool = reference_df.copy()
        for column in RESOLVER_FIELDS:
            if column not in pool.columns:
                pool[column] = None
        pool = pool[RESOLVER_FIELDS]
    else:
        pool = _candidate_pool_online(
            missing_df, timeout, retry_attempts, max_attempts, verbose
        )

    resolved_rows, still_missing_rows, resolved_itemids = _match_rows(
        missing_df, pool
    )

    # Second online pass: references whose application numbers matched
    # nothing (typos, cases known under a different number) can still
    # resolve by casename, but their docname candidates were not fetched
    # in the first pass.
    if reference_df is None and still_missing_rows:
        retry_df = pd.DataFrame(still_missing_rows)
        retry_names = sorted(
            {
                str(name).strip()
                for name, appnos in zip(
                    retry_df["casename"], retry_df["extracted_appnos"]
                )
                if str(name or "").strip() and str(appnos or "").strip()
            }
        )
        extra = []
        for i in range(0, len(retry_names), _CASENAMES_PER_QUERY):
            chunk = retry_names[i : i + _CASENAMES_PER_QUERY]
            extra.extend(
                _fetch_candidates(
                    basic_function("docname", chunk),
                    timeout, retry_attempts, max_attempts, verbose,
                )
            )
        if extra:
            pool = pd.concat(
                [pool, pd.DataFrame(extra)], ignore_index=True
            ).drop_duplicates(subset=["itemid"]).reset_index(drop=True)
            retry_resolved, still_missing_rows, retry_itemids = _match_rows(
                retry_df, pool
            )
            resolved_rows.extend(retry_resolved)
            resolved_itemids |= retry_itemids

    resolved_df = (
        pd.DataFrame(resolved_rows)
        if resolved_rows
        else pd.DataFrame(columns=RESOLVED_COLUMNS)
    )
    still_missing_df = (
        pd.DataFrame(still_missing_rows).reset_index(drop=True)
        if still_missing_rows
        else pd.DataFrame(columns=MISSING_REFERENCE_COLUMNS)
    )
    external_nodes_df = (
        pool[pool["itemid"].isin(resolved_itemids)].reset_index(drop=True)
        if len(pool)
        else pd.DataFrame(columns=RESOLVER_FIELDS)
    )

    if verbose:
        logging.info(
            f"Resolved {len(resolved_df)} of {len(missing_df)} references "
            f"({len(still_missing_df)} still unresolved)"
        )
    return resolved_df, external_nodes_df, still_missing_df
