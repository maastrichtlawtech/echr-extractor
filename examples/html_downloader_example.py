"""Example script for fetching and parsing ECHR HTML full text."""

import argparse
import sys
from pathlib import Path

import requests

try:
    from echr_extractor.ECHR_html_downloader import base_url, get_full_text_from_html
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))
    from echr_extractor.ECHR_html_downloader import base_url, get_full_text_from_html
else:
    repo_root = Path(__file__).resolve().parents[1]


def fetch_html(item_id, timeout):
    response = requests.get(f"{base_url}{item_id}", timeout=timeout)
    response.raise_for_status()
    return response.text


def main():
    parser = argparse.ArgumentParser(
        description="Fetch and parse ECHR full text HTML for a single HUDOC item."
    )
    parser.add_argument(
        "--item-id",
        default="001-57574",
        help="HUDOC itemid, e.g. 001-57574",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=2000,
        help="Max characters to print (ignored with --show-all).",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Print the full parsed text.",
    )
    parser.add_argument(
        "--save-path",
        default="",
        help="Optional path to write the parsed text to a file.",
    )
    args = parser.parse_args()

    html = fetch_html(args.item_id, args.timeout)
    text = get_full_text_from_html(html)

    saved_path = None
    if args.save_path:
        save_path = Path(args.save_path).expanduser()
    else:
        save_path = repo_root / "output" / f"{args.item_id}.txt"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(text, encoding="utf-8")
    saved_path = str(save_path)

    print(f"Item ID: {args.item_id}")
    print(f"Parsed length: {len(text)} characters\n")
    if args.show_all:
        print(text)
    else:
        preview = text[: args.max_chars]
        print(preview)
        if len(text) > len(preview):
            print("\n...[truncated]... (use --show-all to print everything)")
    if saved_path:
        print(f"\nSaved to: {saved_path}")


if __name__ == "__main__":
    main()
