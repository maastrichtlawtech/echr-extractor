import logging
from datetime import datetime, timedelta
import pandas as pd
import requests
import json
import time
import gc
from tqdm import tqdm


def get_r(url, timeout, retry, verbose, max_attempts=20):
    """
    Enhanced get data from a URL with improved error handling and retry logic.

    :param str url: The data source URL.
    :param float timeout: The amount of time to wait for a response each attempt.
    :param int retry: The number of times to retry upon failure.
    :param bool verbose: Whether or not to print extra information.
    :param int max_attempts: Maximum number of attempts before giving up.
    :return: requests.Response object or None if all attempts failed.
    """
    count = 0
    last_exception = None

    while count < max_attempts:
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()  # Raise an exception for bad status codes
            return r
        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as e:
            last_exception = e
            count += 1
            if verbose:
                logging.warning(
                    f"Request failed (attempt {count}/{max_attempts}): {type(e).__name__}: {str(e)}"
                )

            if count <= retry:
                # Exponential backoff
                wait_time = min(2**count, 30)  # Cap at 30 seconds
                if verbose:
                    logging.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                if verbose:
                    logging.error(
                        f"Unable to connect to {url} after {count} attempts. Last error: {last_exception}"
                    )
                return None

    if verbose:
        logging.error(
            f"Max attempts ({max_attempts}) exceeded for {url}. Last error: {last_exception}"
        )
    return None


def get_date_ranges(start_date, end_date, days_per_batch=365):
    """
    Split a date range into smaller batches to prevent timeouts and memory issues.

    :param str start_date: Start date in YYYY-MM-DD format
    :param str end_date: End date in YYYY-MM-DD format
    :param int days_per_batch: Number of days per batch
    :return: List of (start_date, end_date) tuples
    """
    if not start_date or not end_date:
        return [(start_date, end_date)]

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    date_ranges = []
    current_start = start_dt

    while current_start < end_dt:
        current_end = min(current_start + timedelta(days=days_per_batch - 1), end_dt)
        date_ranges.append(
            (current_start.strftime("%Y-%m-%d"), current_end.strftime("%Y-%m-%d"))
        )
        current_start = current_end + timedelta(days=1)

    return date_ranges


def basic_function(term, values):
    values = ['"' + i + '"' for i in values]
    main_body = list()
    cut_term = term.replace('"', "")
    for v in values:
        main_body.append(f"({cut_term}={v}) OR ({cut_term}:{v})")
    query = f"({' OR '.join(main_body)})"
    return query


def link_to_query(link):
    # Fixing brackets
    link = link.replace("%7B", "{")
    link = link.replace("%7D", "}")
    link = link.replace("%5B", "[")
    link = link.replace("%5D", "]")
    link = link.replace("%22", '"')
    link = link.replace("%27", "'")

    # fixing fulltext shenanigans - happen because of people using "
    # in the queries.

    full_text_input = ""
    fulltext_end = -1
    fulltext_start = link.find("fulltext")
    if fulltext_start:
        start = link[fulltext_start:].find("[") + fulltext_start + 1
        fulltext_end = link[fulltext_start:].find("]") + fulltext_start
        fragment_to_fix = link[start:fulltext_end]
        full_text_input = (
            "("
            + "".join(fragment_to_fix.rsplit('"', 1)).replace('"', "", 1)
            + ")".replace("\\", "")
        )
        full_text_input = full_text_input.replace("\\", "")
    # removing first and last " elements and saving the output to
    # put manually later
    if fulltext_end:

        if link[fulltext_end + 1] == ",":
            to_replace = link[fulltext_start - 1 : fulltext_end + 2]
        else:
            to_replace = link[fulltext_start - 1 : fulltext_end + 1]
        link = link.replace(to_replace, "")

    extra_cases_map = {
        "bodyprocedure": (
            '("PROCEDURE" ONEAR(n=1000) terms OR "PROCÉDURE" ONEAR(n=1000) terms)'
        ),
        "bodyfacts": (
            '("THE FACTS" ONEAR(n=1000) terms OR "EN FAIT" ONEAR(n=1000) terms)'
        ),
        "bodycomplaints": (
            '("COMPLAINTS" ONEAR(n=1000) terms OR "GRIEFS" ONEAR(n=1000) terms)'
        ),
        "bodylaw": (
            '("THE LAW" ONEAR(n=1000) terms OR "EN DROIT" ONEAR(n=1000) terms)'
        ),
        "bodyreasons": (
            '("FOR THESE REASONS" ONEAR(n=1000) terms OR '
            '"PAR CES MOTIFS" ONEAR(n=1000) terms)'
        ),
        "bodyseparateopinions": (
            '(("SEPARATE OPINION" OR "SEPARATE OPINIONS") ONEAR(n=5000) terms OR '
            '"OPINION SÉPARÉE" ONEAR(n=5000) terms)'
        ),
        "bodyappendix": (
            '("APPENDIX" ONEAR(n=1000) terms OR "ANNEXE" ONEAR(n=1000) terms)'
        ),
    }

    def full_text_function(term, values):
        return f"({','.join(values)})"

    def date_function(term, values):
        values = ['"' + i + '"' for i in values]
        query = "(kpdate>=first_term AND kpdate<=second_term)"
        first = values[0]
        second = values[1]
        if first == '""':
            first = '"1900-01-01"'
        if second == '""':
            second = str(datetime.today().date())
        query = query.replace("first_term", first)
        query = query.replace("second_term", second)
        return query

    def advanced_function(term, values):
        body = extra_cases_map.get(term)
        query = body.replace("terms", ",".join(values))
        return query

    query_map = {
        "docname": basic_function,
        "appno": basic_function,
        "scl": basic_function,
        "rulesofcourt": basic_function,
        "applicability": basic_function,
        "ecli": basic_function,
        "conclusion": basic_function,
        "resolutionnumber": basic_function,
        "separateopinions": basic_function,
        "externalsources": basic_function,
        "kpthesaurus": basic_function,
        "advopidentifier": basic_function,
        "documentcollectionid2": basic_function,
        "fulltext": full_text_function,
        "kpdate": date_function,
        "bodyprocedure": advanced_function,
        "bodyfacts": advanced_function,
        "bodycomplaints": advanced_function,
        "bodylaw": advanced_function,
        "bodyreasons": advanced_function,
        "bodyseparateopinions": advanced_function,
        "bodyappendix": advanced_function,
        "languageisocode": basic_function,
    }

    start = link.index("{")
    end = link.rindex("}")
    json_str = link[start : end + 1].replace("'", '"')

    try:
        link_dictionary = json.loads(json_str)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON: {json_str}")
        link_dictionary = {}
        pairs = json_str.strip("{}").split(",")
        for pair in pairs:
            key, value = pair.split(":", 1)
            key = key.strip().strip('"')
            value = value.strip().strip("[]").split(",")
            link_dictionary[key] = [v.strip().strip('"') for v in value]

    base_query = (
        "https://hudoc.echr.coe.int/app/query/results?query=contentsitename:ECHR"
        " AND (NOT (doctype=PR OR doctype=HFCOMOLD OR doctype=HECOMOLD)) AND "
        "inPutter&select={select}&sort=itemid%20Ascending&start={start}"
        "&length={length}"
    )
    query_elements = list()
    if full_text_input:
        query_elements.append(full_text_input)
    date_addition = ""
    for key in list(link_dictionary.keys()):
        if key == "kpdate":
            vals = link_dictionary.get(key)
            funct = query_map.get(key)
            date_addition = funct(key, vals)
        elif key == "sort":
            continue
        else:
            vals = link_dictionary.get(key)
            funct = query_map.get(key)
            query_elements.append(funct(key, vals))
    if date_addition:
        query_elements.append(date_addition)
    query_total = " AND ".join(query_elements)
    final_query = base_query.replace("inPutter", query_total)

    return final_query


def determine_meta_url(link, query_payload, start_date, end_date):
    if query_payload:
        META_URL = (
            "http://hudoc.echr.coe.int/app/query/results"
            f"?query={query_payload}"
            "&select={select}"
            + "&sort=itemid Ascending"
            + "&start={start}&length={length}"
        )
    elif link:
        META_URL = link_to_query(link)
    else:
        META_URL = (
            "http://hudoc.echr.coe.int/app/query/results"
            "?query=(contentsitename=ECHR) AND "
            '(documentcollectionid2:"JUDGMENTS" OR '
            'documentcollectionid2:"COMMUNICATEDCASES" OR '
            'documentcollectionid2:"DECISIONS" OR '
            'documentcollectionid2:"CLIN") AND '
            "lang_inputter"
            "&select={select}"
            + "&sort=itemid Ascending"
            + "&start={start}&length={length}"
        )
        if start_date and end_date:
            addition = f'(kpdate>="{start_date}" AND kpdate<="{end_date}")'
        elif start_date:
            end_date = datetime.today().date()
            addition = f'(kpdate>="{start_date}" AND kpdate<="{end_date}")'
        elif end_date:
            start_date = "1900-01-01"
            addition = f'(kpdate>="{start_date}" AND kpdate<="{end_date}")'
        else:
            addition = ""

        if addition:
            addition = " AND " + addition
            META_URL = META_URL.replace("&select", addition + "&select")
    return META_URL


def get_echr_metadata(
    start_id,
    end_id,
    verbose,
    fields,
    start_date,
    end_date,
    link,
    language,
    query_payload,
    # New configuration parameters with defaults for backward compatibility
    batch_size=500,
    timeout=60,
    retry_attempts=3,
    max_attempts=20,
    days_per_batch=365,
    progress_bar=True,
    memory_efficient=True,
):
    """
    Enhanced ECHR metadata extraction with improved batching, error handling, and memory management.

    :param int start_id: The index to start the search from.
    :param int end_id: The index to end search at, where the default fetches all results.
    :param bool verbose: Whether or not to print extra information.
    :param list fields: List of fields to extract.
    :param str start_date: The point from which to save cases (YYYY-MM-DD format).
    :param str end_date: The point before which to save cases (YYYY-MM-DD format).
    :param str link: Custom HUDOC link.
    :param list language: List of language codes.
    :param str query_payload: Custom query payload.
    :param int batch_size: Number of records to fetch per batch (max 500).
    :param float timeout: Request timeout in seconds.
    :param int retry_attempts: Number of retry attempts for failed requests.
    :param int max_attempts: Maximum total attempts before giving up.
    :param int days_per_batch: Number of days per date batch for large date ranges.
    :param bool progress_bar: Whether to show progress bar.
    :param bool memory_efficient: Whether to use memory-efficient processing.
    :return: pandas.DataFrame or False if no data retrieved.
    """
    # Set default fields if not provided
    if not fields:
        fields = [
            "itemid",
            "applicability",
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
            "publishedby",
            "representedby",
            "respondent",
            "separateopinion",
            "sharepointid",
            "externalsources",
            "issue",
            "referencedate",
            "rulesofcourt",
            "DocId",
            "WorkId",
            "Rank",
            "Author",
            "Size",
            "Path",
            "Description",
            "Write",
            "CollapsingStatus",
            "HighlightedSummary",
            "HighlightedProperties",
            "contentclass",
            "PictureThumbnailURL",
            "ServerRedirectedURL",
            "ServerRedirectedEmbedURL",
            "ServerRedirectedPreviewURL",
            "FileExtension",
            "ContentTypeId",
            "ParentLink",
            "ViewsLifeTime",
            "ViewsRecent",
            "SectionNames",
            "SectionIndexes",
            "SiteLogo",
            "SiteDescription",
            "deeplinks",
            "SiteName",
            "IsDocument",
            "LastModifiedTime",
            "FileType",
            "IsContainer",
            "WebTemplate",
            "SecondaryFileExtension",
            "docaclmeta",
            "OriginalPath",
            "EditorOWSUSER",
            "DisplayAuthor",
            "ResultTypeIdList",
            "PartitionId",
            "UrlZone",
            "AAMEnabledManagedProperties",
            "ResultTypeId",
            "rendertemplateid",
        ]

    # Determine if we need date batching
    use_date_batching = start_date and end_date and not link and not query_payload

    if use_date_batching:
        date_ranges = get_date_ranges(start_date, end_date, days_per_batch)
        if verbose:
            logging.info(
                f"Date range split into {len(date_ranges)} batches of {days_per_batch} days each"
            )
    else:
        date_ranges = [(start_date, end_date)]

    all_data = []
    total_processed = 0
    total_failed = 0

    for batch_idx, (batch_start_date, batch_end_date) in enumerate(date_ranges):
        if verbose:
            logging.info(
                f"Processing date batch {batch_idx + 1}/{len(date_ranges)}: {batch_start_date} to {batch_end_date}"
            )

        # Determine meta URL for this batch
        META_URL = determine_meta_url(
            link, query_payload, batch_start_date, batch_end_date
        )

        # URL encoding
        META_URL = META_URL.replace(" ", "%20")
        META_URL = META_URL.replace('"', "%22")
        META_URL = META_URL.replace("%5C", "")

        # Language handling
        language_input = basic_function("languageisocode", language)
        if not link:
            META_URL = META_URL.replace("lang_inputter", language_input)

        META_URL = META_URL.replace("{select}", ",".join(fields))

        # Get total result count for this batch
        url = META_URL.format(start=0, length=1)
        if verbose:
            logging.info(f"Checking result count: {url}")

        r = get_r(url, timeout, retry_attempts, verbose, max_attempts)
        if r is None:
            logging.error(f"Failed to get result count for batch {batch_idx + 1}")
            total_failed += 1
            continue

        try:
            resultcount = r.json()["resultcount"]
            if verbose:
                logging.info(f"Available results for this batch: {resultcount}")
        except (KeyError, ValueError) as e:
            logging.error(f"Failed to parse result count: {e}")
            total_failed += 1
            continue

        if resultcount == 0:
            if verbose:
                logging.info(f"No results found for batch {batch_idx + 1}")
            continue

        # Determine actual end_id for this batch
        batch_end_id = min(end_id, resultcount) if end_id else resultcount
        batch_start_id = start_id if batch_idx == 0 else 0

        if verbose:
            msg = f"Fetching {batch_end_id - batch_start_id} results from index {batch_start_id} to {batch_end_id}"
            if batch_start_date and batch_end_date:
                msg += f" for date range {batch_start_date} to {batch_end_date}"
            logging.info(msg)

        # Process this batch
        batch_data = []
        batch_processed = 0
        batch_failed = 0

        # Create progress bar for this batch
        if progress_bar and (batch_end_id - batch_start_id) > batch_size:
            pbar = tqdm(
                total=batch_end_id - batch_start_id,
                desc=f"Batch {batch_idx + 1}/{len(date_ranges)}",
                unit="records",
                leave=False,
            )

        # Process in batches of batch_size
        for i in range(batch_start_id, batch_end_id, batch_size):
            current_batch_size = min(batch_size, batch_end_id - i)

            if verbose and not progress_bar:
                logging.info(f"Fetching records {i} to {i + current_batch_size}")

            url = META_URL.format(start=i, length=current_batch_size)
            r = get_r(url, timeout, retry_attempts, verbose, max_attempts)

            if r is not None:
                try:
                    temp_dict = r.json()["results"]
                    for result in temp_dict:
                        batch_data.append(result["columns"])
                    batch_processed += len(temp_dict)

                    if progress_bar and (batch_end_id - batch_start_id) > batch_size:
                        pbar.update(len(temp_dict))

                except (KeyError, ValueError) as e:
                    logging.error(f"Failed to parse results: {e}")
                    batch_failed += 1
            else:
                batch_failed += 1
                if progress_bar and (batch_end_id - batch_start_id) > batch_size:
                    pbar.update(current_batch_size)

            # Memory management: process data in chunks if memory_efficient is True
            if memory_efficient and len(batch_data) > 10000:
                all_data.extend(batch_data)
                batch_data = []
                gc.collect()  # Force garbage collection

        # Close progress bar for this batch
        if progress_bar and (batch_end_id - batch_start_id) > batch_size:
            pbar.close()

        # Add remaining batch data
        all_data.extend(batch_data)
        total_processed += batch_processed
        total_failed += batch_failed

        if verbose:
            logging.info(
                f"Batch {batch_idx + 1} completed: {batch_processed} processed, {batch_failed} failed"
            )

    # Final summary
    if verbose:
        logging.info(
            f"Total processing complete: {total_processed} records processed, {total_failed} batches failed"
        )

    if len(all_data) == 0:
        logging.warning("No data retrieved from any batch")
        return False

    # Create DataFrame
    df = pd.DataFrame.from_records(all_data)

    if verbose:
        logging.info(
            f"Created DataFrame with {len(df)} records and {len(df.columns)} columns"
        )

    return df
