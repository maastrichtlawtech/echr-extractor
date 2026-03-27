import re
import threading

import requests
from bs4 import BeautifulSoup

base_url = "https://hudoc.echr.coe.int/app/conversion/docx/html/body?library=ECHR&id="


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


def download_full_text_main(df, threads):
    item_ids = df["itemid"]
    eclis = df["ecli"]
    length = item_ids.size
    if length > threads:
        at_once_threads = int(length / threads)
    else:
        at_once_threads = length
    all_dict = list()
    threads = []
    for i in range(0, length, at_once_threads):
        curr_ids = item_ids[i : (i + at_once_threads)]
        curr_ecli = eclis[i : (i + at_once_threads)]
        t = threading.Thread(
            target=download_full_text_separate, args=(curr_ids, curr_ecli, all_dict)
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


def download_full_text_separate(item_ids, eclis, dict_list):
    full_list = []
    eclis = eclis.reset_index(drop=True)
    item_ids = item_ids.reset_index(drop=True)

    def download_html(item_ids, eclis):
        retry_ids = []
        retry_eclis = []
        for i in range(len(item_ids)):
            item_id = item_ids[i]
            ecli = eclis[i]
            try:
                r = requests.get(base_url + item_id, timeout=1)
                json_dict = {
                    "item_id": item_id,
                    "ecli": ecli,
                    "full_text": get_full_text_from_html(r.text),
                }
                full_list.append(json_dict)
            except Exception:
                retry_ids.append(item_id)
                retry_eclis.append(ecli)
        return retry_ids, retry_eclis

    retry_ids, retry_eclis = download_html(item_ids, eclis)
    download_html(retry_ids, retry_eclis)
    dict_list.append(full_list)
