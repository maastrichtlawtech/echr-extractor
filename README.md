# ECHR Extractor

A powerful Python library for extracting case law data from the European Court of Human Rights (ECHR) HUDOC database. Built for researchers, legal analysts, and data scientists working with European human rights law.

## Features

### Core Functionality
- 📊 **Extract metadata** for ECHR cases from the HUDOC database
- 📄 **Download full text** content for cases with parallel processing
- 📅 **Date range batching** - automatically splits large date ranges to prevent API timeouts
- 🔄 **Intelligent error handling** - exponential backoff retry logic for failed requests
- 💾 **Memory-efficient processing** - chunked processing with garbage collection for large datasets
- 📈 **Progress tracking** - real-time tqdm progress bars for long-running operations
- 🔍 **Text segmentation** - segment full texts into legal sections (procedure, facts, law, operative, etc.)
- 🕸️ **Network analysis** - generate nodes and edges for citation network graphs
- 🌍 **Multiple language support** - English, French, and other ECHR languages
- 📦 **Flexible output formats** - CSV, JSON, and in-memory pandas DataFrames

### Advanced Features
- Custom date ranges and case ID ranges
- Advanced querying with direct HUDOC URLs or query payloads
- Selective field extraction for optimized downloads
- Citation network edge calculation with missing reference tracking
- CLI tool for command-line usage
- Configurable batch sizes, timeouts, and retry parameters

## Installation

```bash
pip install echr-extractor
```

### Dependencies
- Python 3.8+
- requests
- pandas
- beautifulsoup4
- dateparser
- tqdm

## Quick Start

### Installation and Basic Usage

```python
from echr_extractor import get_echr, get_echr_extra, get_nodes_edges, get_echr_segments

# Get basic metadata for 100 English cases
df = get_echr(count=100, language=['ENG'])
print(f"Retrieved {len(df)} cases")

# Get metadata + full text with parallel download
df, full_texts = get_echr_extra(count=100, language=['ENG'], threads=10)

# Generate network data for citation analysis
nodes, edges, missing = get_nodes_edges(df=df)
print(f"Network: {len(nodes)} nodes, {len(edges)} edges")
```

## Core Functions

### `get_echr()` - Extract Metadata

Retrieves metadata for ECHR cases from the HUDOC database with advanced batching and error handling.

**Basic Parameters:**
- `start_id` (int, default: 0): Starting case ID
- `end_id` (int, optional): Ending case ID (fetches all if None)
- `count` (int, optional): Number of cases to download
- `start_date` (str, optional): Start date in YYYY-MM-DD format
- `end_date` (str, optional): End date in YYYY-MM-DD format
- `language` (list, default: ['ENG']): Languages to download
- `fields` (list, optional): Specific metadata fields to extract
- `save_file` (str, default: 'y'): Save to CSV ('y') or return DataFrame ('n')
- `verbose` (bool, default: False): Show detailed progress information

**Advanced Parameters:**
- `batch_size` (int, default: 500): Records per API request (max 500)
- `timeout` (float, default: 60): Request timeout in seconds
- `retry_attempts` (int, default: 3): Number of retry attempts on failure
- `max_attempts` (int, default: 20): Maximum total attempts before giving up
- `days_per_batch` (int, default: 365): Days per batch for date range splitting
- `progress_bar` (bool, default: True): Show tqdm progress bars
- `memory_efficient` (bool, default: True): Use memory-efficient chunked processing
- `link` (str, optional): Direct HUDOC search URL for advanced queries
- `query_payload` (str, optional): Direct API query payload

**Returns:** pandas DataFrame with case metadata (or False on error)

### `get_echr_extra()` - Extract Metadata + Full Text

Retrieves both metadata and full-text content for ECHR cases.

**Additional Parameters:**
- `threads` (int, default: 10): Number of parallel download threads

**Returns:** Tuple of (DataFrame, list of full-text documents)

### `get_nodes_edges()` - Generate Citation Network

Generates nodes and edges for citation network analysis from case metadata.

The network is **self-enclosed by default**: edges only point at documents
present in the corpus you pass in. Citations to cases outside the corpus are
returned (and saved) as a missing-references table with one row per citing
document and unresolved reference, including the parsed application numbers,
casename, year, and language — so out-of-corpus citations are never silently
lost and can be resolved later.

**Parameters:**
- `metadata_path` (str, optional): Path to metadata CSV file
- `df` (DataFrame, optional): Metadata DataFrame (use one of these two)
- `save_file` (str, default: 'y'): Save to files ('y') or return objects ('n')
- `resolve_external` (bool, default: False): Resolve references that point
  outside the corpus by querying HUDOC (batched lookups). Resolved targets are
  added to the edges and their metadata is appended to the nodes with
  `in_corpus=False`
- `reference_df` (DataFrame, optional): Resolve external references offline
  against this larger metadata DataFrame instead of querying HUDOC (composes
  with `resolve_external`: offline first, HUDOC for the remainder)

**Returns:** Tuple of (nodes DataFrame, edges DataFrame, missing references DataFrame)

### `get_document_citations()` - Out-Citations of a Single Document

Parses one document's complete citation list (its `scl` field) and resolves
each cited case to a real HUDOC document.

**Parameters:**
- `itemid` (str, optional): HUDOC itemid; metadata is fetched automatically
- `document` (dict/Series, optional): In-memory document with an `scl` field
- `resolve` (bool, default: True): Resolve citations against HUDOC
- `reference_df` (DataFrame, optional): Resolve offline against this corpus

**Returns:** DataFrame with one row per citation. Resolved rows carry
`resolved_id`, `resolved_itemid`, `resolved_docname`, and `match_method`
(`appno` or `casename`); unresolvable references are kept with empty
resolution columns, never dropped.

### `resolve_references()` / `parse_scl_references()` - Lower-Level Building Blocks

For custom pipelines, the pieces behind the two functions above are exported
directly:

- `parse_scl_references(scl, citing_id=None)` turns a raw `scl` citation
  string into a DataFrame with one row per reference (parsed application
  numbers, casename, year, language)
- `resolve_references(missing_df, reference_df=None)` resolves any such table
  (including the missing-references output of `get_nodes_edges()`) and returns
  `(resolved, external_nodes, still_missing)`. With `reference_df` it works
  fully offline; without it, HUDOC is queried in batches. References are tried
  by application number first, then by casename. `missing_df` must contain all
  of the columns `citing_id`, `missing_references`, `extracted_appnos`,
  `casename`, `year` and `ref_language` (a `ValueError` is raised otherwise) —
  build it with `parse_scl_references()` or `get_nodes_edges()` rather than by
  hand

### `get_echr_segments()` - Segment Full Texts

Segments ECHR full-text documents into structured legal sections. Accepts either the raw outputs from `get_echr_extra()` or a pre-merged DataFrame.

**Parameters:**
- `df` (DataFrame, optional): Metadata DataFrame from `get_echr_extra()`
- `full_texts` (list, optional): Full-text list from `get_echr_extra()`
- `corpus_df` (DataFrame, optional): Pre-merged DataFrame with `itemid`, `languageisocode`, and `fulltext` columns
- `save_file` (str, default: 'y'): Save to CSV ('y') or return DataFrame ('n')
- `allowed_langs` (tuple, default: ('ENG', 'FRE')): Language codes to process
- `min_segment_length` (int, default: 50): Minimum characters for a segment to be kept

**Output columns:** `itemid`, `languageisocode`, `ecli`, `parser_mode`, `procedure`, `facts`, `complaints`, `law`, `operative`, `subject_matter`, `court_assessment`, `separate_opinion`, `appendix`, `num_sections`, `error`

**Supported document types:** Standard judgments, commission decisions, communicated cases, info notes, press releases

## Usage Examples

### Example 1: Extract Recent Cases

```python
from echr_extractor import get_echr

# Get all English cases from the last 3 years
df = get_echr(
    start_date='2021-01-01',
    end_date='2023-12-31',
    language=['ENG'],
    verbose=True
)

print(f"Downloaded {len(df)} cases")
print(f"Columns: {df.columns.tolist()}")
```

### Example 2: Large-Scale Extraction with Batching

```python
from echr_extractor import get_echr

# Extract 10 years of data with automatic date batching
# The library will split this into yearly chunks to avoid timeouts
df = get_echr(
    start_date='2010-01-01',
    end_date='2020-12-31',
    days_per_batch=365,  # Split into 1-year batches
    progress_bar=True,
    memory_efficient=True,
    verbose=True
)

# Save to CSV
df.to_csv('echr_cases_2010_2020.csv', index=False)
```

### Example 3: Extract Specific Fields Only

```python
from echr_extractor import get_echr

# Download only essential fields to reduce data size
fields = [
    'itemid',
    'appno',
    'docname',
    'judgementdate',
    'article',
    'violation'
]

df = get_echr(
    start_id=0,
    count=1000,
    fields=fields,
    language=['ENG']
)

print(df.head())
```

### Example 4: Extract with Full Text

```python
from echr_extractor import get_echr_extra
import json

# Get metadata and full text for recent cases
df, full_texts = get_echr_extra(
    start_date='2022-01-01',
    end_date='2023-12-31',
    language=['ENG'],
    threads=10,  # Use 10 parallel threads
    verbose=True
)

# Save full texts as JSON
with open('full_texts.json', 'w') as f:
    json.dump(full_texts, f, indent=2)

print(f"Retrieved {len(df)} metadata records and {len(full_texts)} full texts")
```

### Example 5: Citation Network Analysis

```python
from echr_extractor import get_echr, get_nodes_edges

# Step 1: Get case metadata
df = get_echr(count=500, language=['ENG'], save_file='n')

# Step 2: Generate network data
nodes, edges, missing = get_nodes_edges(df=df, save_file='y')

print(f"Nodes: {len(nodes)} cases")
print(f"Edges: {len(edges)} citation relationships")
print(f"Missing references: {len(missing)} unresolved citations")

# Network data is now in:
# - data/ECHR_nodes.csv (case information)
# - data/ECHR_edges.csv (citation relationships)
# - data/ECHR_nodes.json (JSON format)
# - data/ECHR_edges.json (JSON format)
# - data/ECHR_missing_references.csv (citations pointing outside the corpus,
#   with parsed appnos/casename/year/language)
```

The network is self-enclosed: edges only connect documents inside your fetch.
To also link citations that point *outside* the corpus, resolve them against
HUDOC (or against a larger offline corpus):

```python
from echr_extractor import get_echr, get_nodes_edges

df = get_echr(start_date='2022-01-10', end_date='2022-01-20', save_file='n')

# Resolve out-of-corpus citations with batched HUDOC lookups
nodes, edges, missing = get_nodes_edges(df=df, save_file='n',
                                        resolve_external=True)

external = nodes[~nodes['in_corpus']]
print(f"{len(external)} cited cases fetched from outside the corpus")
print(f"{len(missing)} references could not be resolved at all")

# Offline alternative: resolve against metadata you already downloaded
# nodes, edges, missing = get_nodes_edges(df=df, reference_df=full_corpus_df)
```

### Example 5b: Out-Citations of a Single Document

```python
from echr_extractor import get_document_citations

# Everything Sanoma Uitgevers B.V. v. the Netherlands [GC] cites
citations = get_document_citations(itemid='001-100448')

resolved = citations[citations['resolved_id'].notna()]
print(f"{len(resolved)} of {len(citations)} citations resolved")
print(resolved[['missing_references', 'resolved_docname', 'match_method']].head())

# Works on in-memory documents too (e.g. a row from get_echr output):
# citations = get_document_citations(document=df.iloc[0])
```

Or from the command line:

```bash
echr-extractor citations --itemid 001-100448
# -> data/echr_citations_001-100448.csv
```

### Example 6: Segment Full Texts into Legal Sections

```python
from echr_extractor import get_echr_extra, get_echr_segments

# Step 1: Download metadata and full text
df, full_texts = get_echr_extra(count=50, language=['ENG'], threads=10)

# Step 2: Segment into legal sections
segments = get_echr_segments(df=df, full_texts=full_texts, save_file='n')

print(f"Segmented {len(segments)} documents")
print(f"Sections found per doc: {segments['num_sections'].mean():.1f} avg")

# Access individual sections
for _, row in segments.head(3).iterrows():
    print(f"\n--- {row['itemid']} ---")
    if row['procedure']:
        print(f"  Procedure: {row['procedure'][:80]}...")
    if row['facts']:
        print(f"  Facts: {row['facts'][:80]}...")
    if row['law']:
        print(f"  Law: {row['law'][:80]}...")
```

### Example 7: Segment Previously Downloaded Data

```python
import json
import pandas as pd
from echr_extractor import get_echr_segments

# Load previously saved data. Saved file names include the fetched
# range, e.g. echr_metadata_0-100_dates_START-END.csv and
# echr_full_text_0-100_dates_START-END.json
df = pd.read_csv('data/echr_metadata_0-100_dates_START-END.csv')
with open('data/echr_full_text_0-100_dates_START-END.json') as f:
    full_texts = json.load(f)

# Segment with custom settings
segments = get_echr_segments(
    df=df,
    full_texts=full_texts,
    allowed_langs=('ENG',),       # English only
    min_segment_length=100,       # Skip very short segments
)

# Filter to documents that have a 'law' section
has_law = segments[segments['law'].notna()]
print(f"{len(has_law)} documents have a 'law' section")
```

### Example 8: Advanced Querying with Query Payloads

```python
from echr_extractor import get_echr

# Search for cases about Article 8 (Right to Private Life)
df = get_echr(
    query_payload='article:8',
    language=['ENG'],
    count=500
)

print(f"Found {len(df)} cases about Article 8")

# Search for multiple conditions. Note: the 'violation' field contains
# the numbers of the violated articles (not YES/NO), so filter for a
# violation of those same articles:
df = get_echr(
    query_payload='article:(8 OR 10) AND (violation:8 OR violation:10)',
    language=['ENG']
)
```

### Example 9: Using Direct HUDOC URLs

```python
from echr_extractor import get_echr

# You can also use direct HUDOC search URLs
# Build a URL in HUDOC, then use the JSON representation
url = 'https://hudoc.echr.coe.int/eng#{%22itemid%22:[%22001-57574%22]}'
df = get_echr(link=url)
```

### Example 10: Multi-Language Extraction

```python
from echr_extractor import get_echr

# Get cases in multiple languages
df = get_echr(
    start_date='2020-01-01',
    end_date='2023-12-31',
    language=['ENG', 'FRE'],  # English and French
    verbose=True
)

# Analyze by language
print(df['languageisocode'].value_counts())
```

### Example 11: Error Handling and Resilience

```python
from echr_extractor import get_echr

# Configure for maximum reliability on slow/unreliable connections
df = get_echr(
    start_id=0,
    end_id=50000,
    timeout=120,              # Longer timeout
    retry_attempts=5,         # More retries
    max_attempts=30,          # More total attempts
    batch_size=250,           # Smaller batches
    memory_efficient=True,
    verbose=True
)
```

## Command Line Interface (CLI)

The package includes a command-line tool for easy access to all features:

```bash
# Extract metadata
echr-extractor extract --count 100 --language ENG --verbose

# Extract metadata and full text
echr-extractor extract-full --count 50 --language ENG --threads 10

# Generate network data (file names include the fetched range)
echr-extractor network --metadata-path data/echr_metadata_0-100_dates_START-END.csv

# Same, but also resolve citations pointing outside the corpus via HUDOC
echr-extractor network --metadata-path data/echr_metadata_0-100_dates_START-END.csv --resolve-external

# List and resolve the out-citations of a single document
echr-extractor citations --itemid 001-100448

# Segment full texts into legal sections
echr-extractor segment \
  --metadata-path data/echr_metadata_0-100_dates_START-END.csv \
  --fulltext-path data/echr_full_text_0-100_dates_START-END.json \
  --allowed-langs ENG FRE \
  --min-segment-length 50

# Show help
echr-extractor --help
```

## Output Files

When `save_file='y'` (default), the library creates a `data/` directory with:

- `echr_metadata_*.csv` - Case metadata (name includes the fetched index/date range)
- `echr_full_text_*.json` - Full case texts (when using `get_echr_extra`)
- `ECHR_nodes.csv` - Network nodes (when using `get_nodes_edges`)
- `ECHR_edges.csv` - Network edges (when using `get_nodes_edges`)
- `ECHR_missing_references.csv` - Unresolved citations with parsed appnos/casename/year/language (when using `get_nodes_edges`)
- `ECHR_resolved_references.csv` - Externally resolved citations (when using `resolve_external` or `reference_df`)
- `echr_citations_<itemid>.csv` - Out-citations of one document (when using the `citations` CLI command)
- `ECHR_segments.csv` - Segmented legal sections (when using `get_echr_segments`)

## Performance Tips

### For Large Datasets
```python
df = get_echr(
    start_date='2010-01-01',
    end_date='2020-12-31',
    batch_size=200,           # Smaller batch size
    days_per_batch=180,       # More frequent date batches
    memory_efficient=True,    # Enable memory optimization
    progress_bar=True         # Track progress
)
```

### For Fast Downloads
```python
df = get_echr(
    count=10000,
    batch_size=500,           # Maximum batch size
    timeout=30,
    progress_bar=False        # Disable progress bars for speed
)
```

### For Reliable Downloads
```python
df = get_echr(
    start_date='2020-01-01',
    end_date='2023-12-31',
    timeout=120,              # Longer timeouts
    retry_attempts=5,         # More retries
    max_attempts=30,          # More total attempts
    batch_size=250,           # Medium batch size
    verbose=True
)
```

## Configuration

### Environment Setup

For development or customization:

```bash
# Clone the repository
git clone https://github.com/maastrichtlawtech/echr-extractor.git
cd echr-extractor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Check linting
flake8 src/echr_extractor
```

## Troubleshooting

### API Timeouts
If you encounter timeout errors with large date ranges:
- Reduce `days_per_batch` (e.g., from 365 to 180 days)
- Increase `timeout` parameter (e.g., to 120 seconds)
- Enable verbose mode to see which batches are failing

```python
df = get_echr(
    start_date='2010-01-01',
    end_date='2020-12-31',
    days_per_batch=180,  # Smaller batches
    timeout=120,         # Longer timeout
    verbose=True
)
```

### Memory Issues
For large datasets, enable memory-efficient mode:

```python
df = get_echr(
    start_id=0,
    end_id=100000,
    memory_efficient=True,  # Enable chunked processing
    batch_size=200,         # Smaller batches
    verbose=True
)
```

### Network Errors
Increase retry attempts and max attempts for unreliable connections:

```python
df = get_echr(
    count=5000,
    retry_attempts=5,  # More retries on failure
    max_attempts=30,   # More total attempts
    timeout=120,       # Longer timeout
    verbose=True
)
```

## FAQ

**Q: How many cases can I download?**
A: The HUDOC database contains ~50,000 cases. You can download all of them, but it's recommended to use date ranges or batching for stability.

**Q: What metadata fields are available?**
A: See [HUDOC Field Documentation](https://www.echr.coe.int/Documents/HUDOC_Fields_ENG.pdf). The library supports all available fields.

**Q: Can I download non-English cases?**
A: Yes! Set `language=['FRE']` for French, or other language codes supported by HUDOC.

**Q: How long does a download take?**
A: It depends on the date range and your network. Large downloads (10+ years) typically take several hours. Use `progress_bar=True` to monitor progress.

**Q: Can I use this with Jupyter notebooks?**
A: Yes! The library works seamlessly in Jupyter environments.

```python
# In Jupyter
from echr_extractor import get_echr

df = get_echr(
    start_date='2020-01-01',
    end_date='2023-12-31',
    progress_bar=True  # Shows nice progress bars in Jupyter
)
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and recent improvements.

## Requirements

- Python 3.8+
- requests >= 2.28.0
- pandas >= 1.3.0
- beautifulsoup4 >= 4.9.0
- dateparser >= 1.0.0
- tqdm >= 4.60.0

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributors

**Original Authors:**
- Benjamin Rodrigues de Miranda
- Chloe Crombach
- Piotr Lewandowski
- Pranav Bapat
- Shashank MC
- Gijs van Dijck

**Recent Contributors:**
- David Wicker (Performance improvements, batching, error handling)

## Citation

If you use this library in your research, please cite:

```bibtex
@software{echr_extractor,
  title={ECHR Extractor: Python Library for European Court of Human Rights Data},
  author={LawTech Lab, Maastricht University},
  url={https://github.com/maastrichtlawtech/echr-extractor},
  year={2024}
}
```

## Support & Issues

For bug reports, feature requests, or questions:
1. **GitHub Issues**: [Create an issue](https://github.com/maastrichtlawtech/echr-extractor/issues)
2. **Documentation**: Check the [wiki](https://github.com/maastrichtlawtech/echr-extractor/wiki)
3. **Email**: lawtech@maastrichtuniversity.nl

## Related Resources

- [HUDOC Database](https://hudoc.echr.coe.int/eng) - Official ECHR case database
- [European Court of Human Rights](https://www.echr.coe.int/) - ECHR official website
- [ECHR Documentation](https://www.echr.coe.int/Documents/) - Technical documentation

## Acknowledgments

This project is maintained by the [LawTech Lab](https://www.maastrichtuniversity.nl/) at Maastricht University.
