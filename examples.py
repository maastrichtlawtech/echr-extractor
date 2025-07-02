"""Example usage of the ECHR Extractor."""

from echr_extractor import get_echr, get_echr_extra, get_nodes_edges


def main():
    """Demonstrate basic usage of the ECHR extractor."""

    print("=== ECHR Extractor Example ===\n")

    # Example 1: Basic metadata extraction
    print("1. Extracting basic metadata for 5 cases...")
    try:
        df = get_echr(count=5, save_file="n", verbose=True)
        print(f"   Successfully extracted {len(df)} cases")
        print(f"   Columns: {list(df.columns)}")
        if len(df) > 0:
            print(f"   First case ID: {df.iloc[0]['itemid']}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50 + "\n")

    # Example 2: Metadata with full text (commented out to avoid long download)
    print("2. Extracting metadata + full text (example - not executed):")
    print("   df, texts = get_echr_extra(count=2, save_file='n')")
    print("   This would download full text for each case")

    print("\n" + "=" * 50 + "\n")

    # Example 3: Network analysis (requires existing data)
    print("3. Network analysis (example - requires existing metadata):")
    print("   nodes, edges = get_nodes_edges(df=df, save_file='n')")
    print("   This would generate network data from case references")

    print("\n" + "=" * 50 + "\n")

    # Example 4: Date range filtering
    print("4. Date range filtering example:")
    print("   df = get_echr(")
    print("       start_date='2023-01-01',")
    print("       end_date='2023-12-31',")
    print("       language=['ENG'],")
    print("       save_file='n'")
    print("   )")

    print("\n" + "=" * 50 + "\n")

    # Example 5: Specific fields
    print("5. Limiting to specific fields:")
    print("   fields = ['itemid', 'title', 'kpdate', 'appno']")
    print("   df = get_echr(count=10, fields=fields, save_file='n')")

    print("\nFor more examples, see the README.md file.")


if __name__ == "__main__":
    main()
