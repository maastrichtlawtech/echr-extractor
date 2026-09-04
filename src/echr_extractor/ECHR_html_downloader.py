import logging
import math
import re
import threading
import time

import requests
from bs4 import BeautifulSoup

base_url = "https://hudoc.echr.coe.int/app/conversion/docx/html/body?library=ECHR&id="
DEFAULT_TIMEOUT_SECONDS = 75
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_MAX_WORKERS = 4
DEFAULT_RETRY_BACKOFF_SECONDS = 2
MAX_RETRY_BACKOFF_SECONDS = 30
RETRYABLE_STATUS_CODES = frozenset(
    {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
)


def _retry_delay(attempt, backoff_seconds):
    """Return the bounded exponential delay before the next attempt."""
    return min(
        max(0, float(backoff_seconds)) * (2 ** max(0, attempt - 1)),
        MAX_RETRY_BACKOFF_SECONDS,
    )


def get_full_text_from_html(html_text):
    # This method turns the html code from the summary page into text
    # It has different cases depending on the first character of the CELEX ID
    # Should only be used for summaries extraction
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()  # rip it out

    def _extract_text(tag):
        br_token = "__HUDOC_BR__"
        for br in tag.find_all("br"):
            br.replace_with(br_token)
        text = tag.get_text(" ", strip=True)
        text = text.replace(br_token, "\n")
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        return text

    def _extract_list_item_text(li_tag):
        li_clone = BeautifulSoup(str(li_tag), "html.parser").find("li")
        if li_clone is None:
            return ""
        for nested in li_clone.find_all(["ol", "ul"]):
            nested.decompose()
        return _extract_text(li_clone)

    body = soup.body or soup
    blocks = []
    for elem in body.find_all(["p", "li"]):
        if elem.name == "p":
            text = _extract_text(elem)
            if text:
                blocks.append(text)
        elif elem.name == "li":
            if elem.find("p"):
                continue
            text = _extract_list_item_text(elem)
            if text:
                blocks.append(text)

    if blocks:
        text = "\n\n".join(blocks)
    else:
        text = soup.get_text(separator="\n")

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def download_full_text_main(
    df,
    threads,
    timeout=DEFAULT_TIMEOUT_SECONDS,
    retry_attempts=DEFAULT_RETRY_ATTEMPTS,
    retry_backoff_seconds=DEFAULT_RETRY_BACKOFF_SECONDS,
):
    item_ids = df["itemid"]
    eclis = df["ecli"]
    length = item_ids.size
    if length == 0:
        return []
    worker_count = max(1, min(int(threads), length, DEFAULT_MAX_WORKERS))
    at_once_threads = math.ceil(length / worker_count)
    all_dict = list()
    threads = []
    for i in range(0, length, at_once_threads):
        curr_ids = item_ids[i : (i + at_once_threads)]
        curr_ecli = eclis[i : (i + at_once_threads)]
        t = threading.Thread(
            target=download_full_text_separate,
            args=(
                curr_ids,
                curr_ecli,
                all_dict,
                timeout,
                retry_attempts,
                retry_backoff_seconds,
            ),
        )
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    json_file = list()
    for item in all_dict:
        if len(item) > 0:
            json_file.extend(item)
    return json_file


def download_full_text_separate(
    item_ids,
    eclis,
    dict_list,
    timeout=DEFAULT_TIMEOUT_SECONDS,
    retry_attempts=DEFAULT_RETRY_ATTEMPTS,
    retry_backoff_seconds=DEFAULT_RETRY_BACKOFF_SECONDS,
):
    full_list = []
    empty_by_id = {}
    permanent_failed_ids = set()
    eclis = eclis.reset_index(drop=True)
    item_ids = item_ids.reset_index(drop=True)

    def download_html(item_ids, eclis):
        retry_ids = []
        retry_eclis = []
        for i in range(len(item_ids)):
            item_id = item_ids[i]
            ecli = eclis[i]
            try:
                r = requests.get(base_url + item_id, timeout=timeout)
                # An error page must not be stored as the document text
                r.raise_for_status()
                full_text = get_full_text_from_html(r.text)
                json_dict = {
                    "item_id": item_id,
                    "ecli": ecli,
                    "full_text": full_text,
                }
                if full_text:
                    empty_by_id.pop(item_id, None)
                    full_list.append(json_dict)
                else:
                    # HUDOC's conversion service can temporarily return a
                    # successful but empty response. Retry it just like a
                    # transport error, while retaining the empty record if
                    # every attempt is empty so metadata alignment is kept.
                    empty_by_id[item_id] = json_dict
                    retry_ids.append(item_id)
                    retry_eclis.append(ecli)
            except requests.exceptions.HTTPError:
                empty_by_id.pop(item_id, None)
                status_code = getattr(r, "status_code", None)
                if status_code in RETRYABLE_STATUS_CODES:
                    logging.warning(
                        "HUDOC full-text request for %s returned transient "
                        "HTTP %s; scheduling a retry",
                        item_id,
                        status_code,
                    )
                    retry_ids.append(item_id)
                    retry_eclis.append(ecli)
                else:
                    permanent_failed_ids.add(item_id)
                    logging.warning(
                        "HUDOC full-text request for %s returned non-retryable "
                        "HTTP %s",
                        item_id,
                        status_code,
                    )
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as error:
                empty_by_id.pop(item_id, None)
                logging.warning(
                    "HUDOC full-text request for %s failed with %s; "
                    "scheduling a retry",
                    item_id,
                    type(error).__name__,
                )
                retry_ids.append(item_id)
                retry_eclis.append(ecli)
            except requests.exceptions.RequestException as error:
                empty_by_id.pop(item_id, None)
                logging.warning(
                    "HUDOC full-text request for %s failed with %s; "
                    "scheduling a retry",
                    item_id,
                    type(error).__name__,
                )
                retry_ids.append(item_id)
                retry_eclis.append(ecli)
        return retry_ids, retry_eclis

    retry_ids, retry_eclis = item_ids, eclis
    attempts = max(1, int(retry_attempts))
    for attempt in range(1, attempts + 1):
        retry_ids, retry_eclis = download_html(retry_ids, retry_eclis)
        if not retry_ids:
            break
        if attempt < attempts:
            delay = _retry_delay(attempt, retry_backoff_seconds)
            logging.info(
                "Retrying %s HUDOC full-text request(s) in %.1f seconds "
                "(attempt %s/%s)",
                len(retry_ids),
                delay,
                attempt + 1,
                attempts,
            )
            if delay:
                time.sleep(delay)
    empty_ids = [item_id for item_id in retry_ids if item_id in empty_by_id]
    failed_ids = sorted(
        permanent_failed_ids
        | {item_id for item_id in retry_ids if item_id not in empty_by_id}
    )
    if failed_ids:
        logging.warning(
            f"Full text could not be downloaded for {len(failed_ids)} "
            f"document(s): {failed_ids}"
        )
    if empty_ids:
        full_list.extend(empty_by_id[item_id] for item_id in empty_ids)
        logging.warning(
            f"No HTML text available (kept with empty full_text) for "
            f"{len(empty_ids)} document(s): {empty_ids}"
        )
    dict_list.append(full_list)
