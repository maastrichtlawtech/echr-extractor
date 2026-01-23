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
from echr_extractor import get_echr, get_echr_extra, get_nodes_edges

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

**Parameters:**
- `metadata_path` (str, optional): Path to metadata CSV file
- `df` (DataFrame, optional): Metadata DataFrame (use one of these two)
- `save_file` (str, default: 'y'): Save to files ('y') or return objects ('n')

**Returns:** Tuple of (nodes DataFrame, edges DataFrame, missing references DataFrame)

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
```

### Example 6: Advanced Querying with Query Payloads

```python
from echr_extractor import get_echr

# Search for cases about Article 8 (Right to Private Life)
df = get_echr(
    query_payload='article:8',
    language=['ENG'],
    count=500
)

print(f"Found {len(df)} cases about Article 8")

# Search for multiple conditions
df = get_echr(
    query_payload='article:(8 OR 10) AND violation:YES',
    language=['ENG']
)
```

### Example 7: Using Direct HUDOC URLs

```python
from echr_extractor import get_echr

# You can also use direct HUDOC search URLs
# Build a URL in HUDOC, then use the JSON representation
url = 'https://hudoc.echr.coe.int/eng#{%22itemid%22:[%22001-57574%22]}'
df = get_echr(link=url)
```

### Example 8: Multi-Language Extraction

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

### Example 9: Error Handling and Resilience

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

# Generate network data
echr-extractor network --metadata-path data/echr_metadata.csv

# Show help
echr-extractor --help
```

## Output Files

When `save_file='y'` (default), the library creates a `data/` directory with:

- `ECHR_metadata_*.csv` - Case metadata
- `ECHR_full_text_*.json` - Full case texts (when using `get_echr_extra`)
- `ECHR_nodes.csv` - Network nodes (when using `get_nodes_edges`)
- `ECHR_edges.csv` - Network edges (when using `get_nodes_edges`)
- `ECHR_missing_references.csv` - Unresolved citations (when using `get_nodes_edges`)

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
