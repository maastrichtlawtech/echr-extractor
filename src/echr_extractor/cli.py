"""Command-line interface for ECHR Extractor."""

import argparse
import sys

from . import (
    get_document_citations,
    get_echr,
    get_echr_extra,
    get_echr_segments,
    get_nodes_edges,
)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract case law data from ECHR HUDOC database"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Basic extraction command
    extract_parser = subparsers.add_parser("extract", help="Extract ECHR metadata")
    add_common_args(extract_parser)

    # Full extraction command
    extract_full_parser = subparsers.add_parser(
        "extract-full", help="Extract ECHR metadata and full text"
    )
    add_common_args(extract_full_parser)
    extract_full_parser.add_argument(
        "--threads",
        type=int,
        default=10,
        help="Number of threads for parallel download (default: 10)",
    )

    # Network analysis command
    network_parser = subparsers.add_parser(
        "network", help="Generate nodes and edges for network analysis"
    )
    network_parser.add_argument(
        "--metadata-path", type=str, help="Path to metadata CSV file"
    )
    network_parser.add_argument(
        "--no-save", action="store_true", help="Don't save files, return objects only"
    )
    network_parser.add_argument(
        "--resolve-external",
        action="store_true",
        help="Resolve references pointing outside the corpus via HUDOC",
    )

    # Single-document citations command
    citations_parser = subparsers.add_parser(
        "citations", help="List and resolve the out-citations of one document"
    )
    citations_parser.add_argument(
        "--itemid", type=str, required=True, help="HUDOC itemid of the document"
    )
    citations_parser.add_argument(
        "--no-resolve",
        action="store_true",
        help="Only parse the citations, do not resolve them against HUDOC",
    )
    citations_parser.add_argument(
        "--no-save", action="store_true", help="Don't save files, print summary only"
    )

    # Segmentation command
    segment_parser = subparsers.add_parser(
        "segment", help="Segment ECHR full texts into legal sections"
    )
    segment_parser.add_argument(
        "--metadata-path", type=str, required=True, help="Path to metadata CSV file"
    )
    segment_parser.add_argument(
        "--fulltext-path", type=str, required=True, help="Path to full-text JSON file"
    )
    segment_parser.add_argument(
        "--no-save", action="store_true", help="Don't save files, return objects only"
    )
    segment_parser.add_argument(
        "--min-segment-length",
        type=int,
        default=50,
        help="Minimum segment length in chars (default: 50)",
    )
    segment_parser.add_argument(
        "--allowed-langs",
        nargs="+",
        default=["ENG", "FRE"],
        help="Languages to process (default: ENG FRE)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "extract":
            result = get_echr(
                start_id=args.start_id,
                end_id=args.end_id,
                count=args.count,
                start_date=args.start_date,
                end_date=args.end_date,
                verbose=args.verbose,
                save_file="n" if args.no_save else "y",
                fields=args.fields,
                language=args.language,
            )
            print(f"Extracted {len(result)} cases")

        elif args.command == "extract-full":
            df, texts = get_echr_extra(
                start_id=args.start_id,
                end_id=args.end_id,
                count=args.count,
                start_date=args.start_date,
                end_date=args.end_date,
                verbose=args.verbose,
                save_file="n" if args.no_save else "y",
                threads=args.threads,
                fields=args.fields,
                language=args.language,
            )
            print(f"Extracted {len(df)} cases with full text")

        elif args.command == "network":
            nodes, edges, missing_df = get_nodes_edges(
                metadata_path=args.metadata_path,
                save_file="n" if args.no_save else "y",
                resolve_external=args.resolve_external,
            )
            print(f"Generated {len(nodes)} nodes and {len(edges)} edges")
            if missing_df is not None and len(missing_df) > 0:
                print(f"Found {len(missing_df)} missing references")

        elif args.command == "citations":
            result = get_document_citations(
                itemid=args.itemid, resolve=not args.no_resolve
            )
            resolved_count = (
                result["resolved_id"].notna().sum()
                if "resolved_id" in result.columns
                else 0
            )
            print(
                f"Found {len(result)} citations for {args.itemid} "
                f"({resolved_count} resolved)"
            )
            if not args.no_save and len(result) > 0:
                import os as os_mod
                from pathlib import Path as Path_mod

                Path_mod("data").mkdir(parents=True, exist_ok=True)
                out = os_mod.path.join(
                    "data", f"echr_citations_{args.itemid}.csv"
                )
                result.to_csv(out, index=False)
                print(f"Saved to {out}")

        elif args.command == "segment":
            import json as json_mod

            import pandas as pd

            df = pd.read_csv(args.metadata_path)
            with open(args.fulltext_path) as f:
                full_texts = json_mod.load(f)
            result = get_echr_segments(
                df=df,
                full_texts=full_texts,
                save_file="n" if args.no_save else "y",
                allowed_langs=tuple(args.allowed_langs),
                min_segment_length=args.min_segment_length,
            )
            print(f"Segmented {len(result)} documents into legal sections")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments to a parser."""
    parser.add_argument(
        "--start-id",
        type=int,
        default=0,
        help="ID of first case to download (default: 0)",
    )
    parser.add_argument("--end-id", type=int, help="ID of last case to download")
    parser.add_argument(
        "--count", type=int, help="Number of cases per language to download"
    )
    parser.add_argument(
        "--start-date", type=str, help="Start publication date (yyyy-mm-dd)"
    )
    parser.add_argument(
        "--end-date", type=str, help="End publication date (yyyy-mm-dd)"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show progress information"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Don't save files, return objects only"
    )
    parser.add_argument("--fields", nargs="+", help="Limit metadata fields to download")
    parser.add_argument(
        "--language",
        nargs="+",
        default=["ENG"],
        help="Languages to download (default: ENG)",
    )


if __name__ == "__main__":
    main()
