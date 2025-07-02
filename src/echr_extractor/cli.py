"""Command-line interface for ECHR Extractor."""

import argparse
import sys

from . import get_echr, get_echr_extra, get_nodes_edges


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract case law data from ECHR HUDOC database"
    )

    subparsers = parser.add_subparsers(dest="command",
                                       help="Available commands")

    # Basic extraction command
    extract_parser = subparsers.add_parser("extract",
                                           help="Extract ECHR metadata")
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
        "--no-save", action="store_true",
        help="Don't save files, return objects only"
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
            nodes, edges = get_nodes_edges(
                metadata_path=args.metadata_path,
                save_file="n" if args.no_save else "y"
            )
            print(f"Generated {len(nodes)} nodes and {len(edges)} edges")

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
    parser.add_argument("--end-id", type=int,
                        help="ID of last case to download")
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
        "--no-save", action="store_true",
        help="Don't save files, return objects only"
    )
    parser.add_argument("--fields", nargs="+",
                        help="Limit metadata fields to download")
    parser.add_argument(
        "--language",
        nargs="+",
        default=["ENG"],
        help="Languages to download (default: ENG)",
    )


if __name__ == "__main__":
    main()
