import json
import logging
import os
from pathlib import Path

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


def get_nodes_edges(metadata_path=None, df=None, save_file="y"):
    nodes, edges = echr_nodes_edges(metadata_path=metadata_path, data=df)
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
        return nodes, edges

    return nodes, edges
