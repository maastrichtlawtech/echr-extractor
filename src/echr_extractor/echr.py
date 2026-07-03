import json
import logging
import os
from pathlib import Path

import pandas as pd

from .ECHR_html_downloader import download_full_text_main
from .ECHR_metadata_harvester import get_echr_metadata
from .ECHR_nodes_edges_list_transform import echr_nodes_edges

"""
Enhanced ECHR data extraction with improved batching, error handling, and memory management.

Key improvements:
- Date range batching for large datasets to prevent timeouts
- Enhanced error handling with exponential backoff
- Progress tracking with tqdm progress bars
- Memory-efficient processing for large datasets
- Configurable batch sizes and retry parameters
- Better logging and status reporting

The original functionality is preserved for backward compatibility.
"""


def get_echr(
    start_id=0,
    end_id=None,
    start_date=None,
    count=None,
    end_date=None,
    verbose=False,
    save_file="y",
    fields=None,
    link=None,
    language=None,
    query_payload=None,
    # New configuration parameters
    batch_size=500,
    timeout=60,
    retry_attempts=3,
    max_attempts=20,
    days_per_batch=365,
    progress_bar=True,
    memory_efficient=True,
):
    """
    Enhanced ECHR metadata extraction with improved reliability and performance.

    This function provides a high-level interface for extracting ECHR metadata with
    advanced features like date batching, progress tracking, and memory management.

    :param int start_id: The index to start the search from (default: 0).
    :param int end_id: The index to end search at, where None fetches all results.
    :param str start_date: The point from which to save cases (YYYY-MM-DD format).
    :param int count: Number of records to fetch (alternative to end_id).
    :param str end_date: The point before which to save cases (YYYY-MM-DD format).
    :param bool verbose: Whether or not to print extra information (default: False).
    :param str save_file: Whether to save results to file ("y" or "n", default: "y").
    :param list fields: List of fields to extract (default: None, uses all fields).
    :param str link: Custom HUDOC link for advanced queries.
    :param list language: List of language codes (default: ["ENG"]).
    :param str query_payload: Custom query payload for advanced searches.
    :param int batch_size: Number of records to fetch per batch, max 500 (default: 500).
    :param float timeout: Request timeout in seconds (default: 60).
    :param int retry_attempts: Number of retry attempts for failed requests (default: 3).
    :param int max_attempts: Maximum total attempts before giving up (default: 20).
    :param int days_per_batch: Number of days per date batch for large date ranges (default: 365).
    :param bool progress_bar: Whether to show progress bar (default: True).
    :param bool memory_efficient: Whether to use memory-efficient processing (default: True).

    :return: pandas.DataFrame containing the extracted metadata, or False if extraction failed.

    Example:
        # Basic usage (backward compatible)
        df = get_echr(start_id=0, end_id=1000, verbose=True)

        # Advanced usage with date batching
        df = get_echr(
            start_date='2020-01-01',
            end_date='2023-12-31',
            batch_size=250,
            days_per_batch=180,
            progress_bar=True
        )

        # Memory-efficient processing for large datasets
        df = get_echr(
            start_id=0,
            end_id=50000,
            memory_efficient=True,
            batch_size=200
        )
    """
    if language is None:
        language = ["ENG"]
    if count:
        end_id = int(start_id) + count
        if verbose:
            logging.info(f"--- STARTING ECHR DOWNLOAD FOR {count} RECORDS ---")
    else:
        if verbose:
            logging.info("--- STARTING ECHR DOWNLOAD ---")

    df = get_echr_metadata(
        start_id=start_id,
        end_id=end_id,
        start_date=start_date,
        end_date=end_date,
        verbose=verbose,
        fields=fields,
        link=link,
        language=language,
        query_payload=query_payload,
        batch_size=batch_size,
        timeout=timeout,
        retry_attempts=retry_attempts,
        max_attempts=max_attempts,
        days_per_batch=days_per_batch,
        progress_bar=progress_bar,
        memory_efficient=memory_efficient,
    )
    if df is False:
        return False
    if save_file == "y":
        filename = determine_filename(start_id, end_id, start_date, end_date)
        Path("data").mkdir(parents=True, exist_ok=True)
        file_path = os.path.join("data", filename + ".csv")
        df.to_csv(file_path, index=False)
        logging.info("\n--- DONE ---")
        return df
    else:
        logging.info("\n--- DONE ---")
        return df


def determine_filename(start_id, end_id, start_date, end_date):
    if end_id:
        if start_date and end_date:
            filename = (
                f"echr_metadata_index_{start_id}-{end_id}_dates_{start_date}-{end_date}"
            )
        elif start_date:
            filename = f"echr_metadata_{start_id}-{end_id}_dates_{start_date}-END"
        elif end_date:
            filename = f"echr_metadata_{start_id}-{end_id}_datesSTART-{end_date}"
        else:
            filename = f"echr_metadata_{start_id}-{end_id}_dates_START-END"
    else:
        if start_date and end_date:
            filename = (
                f"echr_metadata_index_{start_id}-ALL_dates_{start_date}-{end_date}"
            )
        elif start_date:
            filename = f"echr_metadata_{start_id}-ALL_dates_{start_date}-END"
        elif end_date:
            filename = f"echr_metadata_{start_id}-ALL_dates_START-{end_date}"
        else:
            filename = f"echr_metadata_{start_id}-ALL_dates_START-END"
    return filename


def get_echr_extra(
    start_id=0,
    end_id=None,
    start_date=None,
    count=None,
    end_date=None,
    verbose=False,
    save_file="y",
    threads=10,
    fields=None,
    link=None,
    language=None,
    query_payload=None,
    # New configuration parameters
    batch_size=500,
    timeout=60,
    retry_attempts=3,
    max_attempts=20,
    days_per_batch=365,
    progress_bar=True,
    memory_efficient=True,
):
    """
    Enhanced ECHR metadata and full-text extraction with improved reliability and performance.

    This function extracts both metadata and full-text content from ECHR cases with
    advanced features like date batching, progress tracking, and memory management.

    :param int start_id: The index to start the search from (default: 0).
    :param int end_id: The index to end search at, where None fetches all results.
    :param str start_date: The point from which to save cases (YYYY-MM-DD format).
    :param int count: Number of records to fetch (alternative to end_id).
    :param str end_date: The point before which to save cases (YYYY-MM-DD format).
    :param bool verbose: Whether or not to print extra information (default: False).
    :param str save_file: Whether to save results to file ("y" or "n", default: "y").
    :param int threads: Number of threads for full-text download (default: 10).
    :param list fields: List of fields to extract (default: None, uses all fields).
    :param str link: Custom HUDOC link for advanced queries.
    :param list language: List of language codes (default: ["ENG"]).
    :param str query_payload: Custom query payload for advanced searches.
    :param int batch_size: Number of records to fetch per batch, max 500 (default: 500).
    :param float timeout: Request timeout in seconds (default: 60).
    :param int retry_attempts: Number of retry attempts for failed requests (default: 3).
    :param int max_attempts: Maximum total attempts before giving up (default: 20).
    :param int days_per_batch: Number of days per date batch for large date ranges (default: 365).
    :param bool progress_bar: Whether to show progress bar (default: True).
    :param bool memory_efficient: Whether to use memory-efficient processing (default: True).

    :return: tuple of (pandas.DataFrame, list) containing metadata and full-text data,
             or (False, False) if extraction failed.
    """
    # Mirror get_echr's count handling so saved file names match the ones
    # get_echr would produce for the same parameters (e.g. 0-100, not 0-ALL)
    if count:
        end_id = int(start_id) + count
    df = get_echr(
        start_id=start_id,
        end_id=end_id,
        start_date=start_date,
        end_date=end_date,
        verbose=verbose,
        count=count,
        save_file="n",
        fields=fields,
        link=link,
        language=language,
        query_payload=query_payload,
        batch_size=batch_size,
        timeout=timeout,
        retry_attempts=retry_attempts,
        max_attempts=max_attempts,
        days_per_batch=days_per_batch,
        progress_bar=progress_bar,
        memory_efficient=memory_efficient,
    )
    logging.info("Full-text download will now begin")
    if df is False:
        return False, False
    json_list = download_full_text_main(df, threads)
    logging.info("Full-text download finished")
    if save_file == "y":
        filename = determine_filename(start_id, end_id, start_date, end_date)
        filename_json = filename.replace("metadata", "full_text")
        Path("data").mkdir(parents=True, exist_ok=True)
        file_path = os.path.join("data", filename + ".csv")
        df.to_csv(file_path, index=False)
        file_path_json = os.path.join("data", filename_json + ".json")
        with open(file_path_json, "w") as f:
            json.dump(json_list, f)
        return df, json_list
    else:
        return df, json_list


def get_nodes_edges(
    metadata_path=None,
    df=None,
    save_file="y",
    resolve_external=False,
    reference_df=None,
):
    """Build the citation network for a metadata corpus.

    The network is self-enclosed by default: edges only point at
    documents present in the corpus. References to cases outside it are
    returned in the third value (one row per citing document and
    unresolved reference, with the parsed application numbers, casename,
    year and language).

    :param str metadata_path: Path to a metadata CSV file.
    :param pd.DataFrame df: Metadata DataFrame (alternative to path).
    :param str save_file: Whether to save results to data/ ("y"/"n").
    :param bool resolve_external: Resolve references that point outside
        the corpus by querying HUDOC (batched appno/casename lookups).
        Resolved targets are added to the edges, and their metadata is
        appended to the nodes with in_corpus=False.
    :param pd.DataFrame reference_df: Resolve external references
        offline against this larger metadata DataFrame instead of (or
        before) querying HUDOC. Composes with resolve_external: offline
        first, then HUDOC for the remainder.
    :return: tuple (nodes, edges, missing_df). missing_df contains only
        the references that stayed unresolved.
    """
    nodes, edges, missing_df = echr_nodes_edges(metadata_path=metadata_path, data=df)
    if isinstance(nodes, str):
        # echr_nodes_edges could not produce a network (no/bad input)
        return nodes, edges, missing_df

    resolved_df = None
    if reference_df is not None or resolve_external:
        from .ECHR_reference_resolver import resolve_references

        resolved_parts, external_parts = [], []
        still_missing = missing_df
        if reference_df is not None and len(still_missing) > 0:
            resolved, external, still_missing = resolve_references(
                still_missing, reference_df=reference_df
            )
            resolved_parts.append(resolved)
            external_parts.append(external)
        if resolve_external and len(still_missing) > 0:
            resolved, external, still_missing = resolve_references(still_missing)
            resolved_parts.append(resolved)
            external_parts.append(external)

        resolved_df = (
            pd.concat(resolved_parts, ignore_index=True)
            if resolved_parts
            else pd.DataFrame()
        )
        external_nodes = (
            pd.concat(external_parts, ignore_index=True).drop_duplicates(
                subset=["itemid"]
            )
            if external_parts
            else pd.DataFrame()
        )
        missing_df = still_missing

        if len(resolved_df) > 0:
            edges = _merge_resolved_into_edges(edges, resolved_df)
            nodes = _append_external_nodes(nodes, external_nodes)
            logging.info(
                f"Resolved {len(resolved_df)} external references to "
                f"{len(external_nodes)} documents; "
                f"{len(missing_df)} references remain unresolved"
            )

    if save_file == "y":
        Path("data").mkdir(parents=True, exist_ok=True)
        edges.to_csv(
            os.path.join("data", "ECHR_edges.csv"), index=False, encoding="utf-8"
        )
        nodes.to_csv(
            os.path.join("data", "ECHR_nodes.csv"), index=False, encoding="utf-8"
        )
        nodes.to_json(os.path.join("data", "ECHR_nodes.json"), orient="records")
        edges.to_json(os.path.join("data", "ECHR_edges.json"), orient="records")
        if missing_df is not None and len(missing_df) > 0:
            missing_df.to_csv(
                os.path.join("data", "ECHR_missing_references.csv"),
                index=False,
                encoding="utf-8",
            )
        if resolved_df is not None and len(resolved_df) > 0:
            resolved_df.to_csv(
                os.path.join("data", "ECHR_resolved_references.csv"),
                index=False,
                encoding="utf-8",
            )

    return nodes, edges, missing_df


def _merge_resolved_into_edges(edges, resolved_df):
    """Union resolved external targets into the per-case reference lists."""
    edges_map = {
        row["ecli"]: set(row["references"]) for _, row in edges.iterrows()
    }
    for citing_id, group in resolved_df.groupby("citing_id"):
        targets = set(group["resolved_id"]) - {citing_id}
        if targets:
            edges_map.setdefault(citing_id, set()).update(targets)
    merged = pd.DataFrame(
        {
            "ecli": sorted(edges_map),
            "references": [sorted(edges_map[k]) for k in sorted(edges_map)],
        }
    )
    return merged


def _append_external_nodes(nodes, external_nodes):
    """Append resolved out-of-corpus documents, flagged in_corpus=False."""
    from .ECHR_nodes_edges_list_transform import node_identifier

    nodes = nodes.assign(in_corpus=True)
    if len(external_nodes) == 0:
        return nodes
    corpus_itemids = (
        set(nodes["itemid"].astype(str)) if "itemid" in nodes.columns else set()
    )
    corpus_ids = set(
        nodes.apply(
            lambda row: node_identifier(row.get("ecli"), row.get("itemid")),
            axis=1,
        )
    )
    external = external_nodes[
        ~external_nodes["itemid"].astype(str).isin(corpus_itemids)
    ].copy()
    external = external[
        ~external.apply(
            lambda row: node_identifier(row.get("ecli"), row.get("itemid")),
            axis=1,
        ).isin(corpus_ids)
    ]
    return pd.concat(
        [nodes, external.assign(in_corpus=False)], ignore_index=True
    )


def get_document_citations(
    itemid=None,
    document=None,
    resolve=True,
    reference_df=None,
    verbose=False,
):
    """Full out-citation list of a single document.

    Parses the document's scl field into one row per cited case and,
    unless resolve=False, resolves each citation to a real HUDOC
    document (offline against reference_df when given, otherwise via
    batched HUDOC queries). Unresolvable references are kept with empty
    resolution columns rather than dropped.

    :param str itemid: HUDOC itemid; the document's metadata (including
        scl) is fetched automatically.
    :param document: Alternatively, an in-memory mapping/Series with an
        'scl' field (and optionally ecli/itemid).
    :param bool resolve: Whether to resolve the parsed references.
    :param pd.DataFrame reference_df: Optional offline reference corpus.
    :return: DataFrame with one row per citation; resolved rows carry
        resolved_id, resolved_itemid, resolved_docname, match_method.

    Example:
        citations = get_document_citations(itemid='001-100448')
        resolved = citations[citations['resolved_id'].notna()]
    """
    from .ECHR_nodes_edges_list_transform import node_identifier
    from .ECHR_reference_resolver import (
        parse_scl_references,
        resolve_references,
    )

    if itemid is None and document is None:
        raise ValueError("Provide either itemid or document")

    if document is None:
        link = (
            "https://hudoc.echr.coe.int/eng#"
            f'{{"itemid":["{itemid}"]}}'
        )
        fetched = get_echr(
            link=link,
            save_file="n",
            progress_bar=False,
            verbose=verbose,
            fields=["itemid", "ecli", "docname", "languageisocode", "scl"],
        )
        if fetched is False or len(fetched) == 0:
            logging.warning(f"No document found for itemid {itemid}")
            return pd.DataFrame()
        document = fetched.iloc[0]

    citing_id = node_identifier(
        document.get("ecli"), document.get("itemid")
    )
    references = parse_scl_references(document.get("scl"), citing_id=citing_id)
    if not resolve or len(references) == 0:
        return references

    resolved, _, still_missing = resolve_references(
        references, reference_df=reference_df, verbose=verbose
    )
    return pd.concat([resolved, still_missing], ignore_index=True)


def prepare_echr_corpus(df, full_texts):
    """Merge metadata DataFrame with full-text data for segmentation.

    Combines the separate metadata and full-text outputs from
    get_echr_extra() into a single DataFrame suitable for
    segment_echr_texts().

    :param pd.DataFrame df: Metadata DataFrame from get_echr() or get_echr_extra().
    :param list full_texts: List of full-text dicts from get_echr_extra(),
        each with keys 'item_id', 'ecli', 'full_text'.
    :return: DataFrame with metadata columns plus 'fulltext' column.

    Example:
        df, full_texts = get_echr_extra(count=100)
        corpus = prepare_echr_corpus(df, full_texts)
        # corpus now has a 'fulltext' column ready for segmentation
    """
    from .segmentation import prepare_segmentation_corpus

    if df is False or not full_texts:
        logging.warning("Cannot prepare corpus: invalid input")
        return pd.DataFrame()

    return prepare_segmentation_corpus(df=df, full_texts=full_texts)


def get_echr_segments(
    df=None,
    full_texts=None,
    corpus_df=None,
    document=None,
    documents=None,
    save_file="y",
    allowed_langs=("ENG", "FRE"),
    min_segment_length=50,
):
    """Segment ECHR documents into structured legal sections.

    Accepts either:
    - A pre-merged DataFrame with 'fulltext' column (via corpus_df)
    - The separate outputs from get_echr_extra() (via df and full_texts)
    - A single in-memory document dict/string (via document)
    - A list of in-memory document dicts (via documents)

    :param pd.DataFrame df: Metadata DataFrame from get_echr_extra().
    :param list full_texts: Full-text list from get_echr_extra().
    :param pd.DataFrame corpus_df: Pre-merged DataFrame with 'fulltext' column.
    :param dict|str document: Single in-memory document or raw text.
    :param list documents: Sequence of in-memory document dicts.
    :param str save_file: Whether to save results to CSV ("y" or "n", default: "y").
    :param tuple allowed_langs: Language codes to process (default: ('ENG', 'FRE')).
    :param int min_segment_length: Minimum segment length in chars (default: 50).
    :return: DataFrame with segmented sections.

    Example:
        # From get_echr_extra output
        df, full_texts = get_echr_extra(count=100)
        segments = get_echr_segments(df=df, full_texts=full_texts)

        # From pre-merged corpus
        from echr_extractor.echr import prepare_echr_corpus
        corpus = prepare_echr_corpus(df, full_texts)
        segments = get_echr_segments(corpus_df=corpus, save_file='n')
    """
    from .segmentation import segment_documents

    try:
        result = segment_documents(
            corpus_df=corpus_df,
            df=df,
            full_texts=full_texts,
            document=document,
            documents=documents,
            allowed_langs=allowed_langs,
            min_segment_length=min_segment_length,
        )
    except ValueError as exc:
        logging.error("%s", exc)
        return pd.DataFrame()

    if save_file == "y":
        Path("data").mkdir(parents=True, exist_ok=True)
        file_path = os.path.join("data", "echr_segments.csv")
        result.to_csv(file_path, index=False)
        logging.info("Segments saved to %s", file_path)

    return result
