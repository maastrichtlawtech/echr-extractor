# ECHR Extractor

Python library for extracting case law data from the European Court of Human Rights (ECHR) HUDOC database.

## Features

- Extract metadata for ECHR cases from the HUDOC database
- Download full text content for cases
- Support for custom date ranges and case ID ranges
- Multiple language support
- Generate nodes and edges for network analysis
- Flexible output formats (CSV, JSON, in-memory DataFrames)

## Installation

```bash
pip install echr-extractor
```

## Quick Start

```python
from echr_extractor import get_echr, get_echr_extra, get_nodes_edges

# Get basic metadata for cases
df = get_echr(start_id=0, count=100, language=['ENG'])

# Get metadata + full text
df, full_texts = get_echr_extra(start_id=0, count=100, language=['ENG'])

# Generate network data
nodes, edges = get_nodes_edges(df=df)
```

## Functions

### `get_echr`

Gets all available metadata for ECHR cases from the HUDOC database.

**Parameters:**
- `start_id` (int, optional): The ID of the first case to download (default: 0)
- `end_id` (int, optional): The ID of the last case to download (default: maximum available)
- `count` (int, optional): Number of cases per language to download (default: None)
- `start_date` (str, optional): Start publication date (yyyy-mm-dd) (default: None)
- `end_date` (str, optional): End publication date (yyyy-mm-dd) (default: current date)
- `verbose` (bool, optional): Show progress information (default: False)
- `fields` (list, optional): Limit metadata fields to download (default: all fields)
- `save_file` (str, optional): Save as CSV file ('y') or return DataFrame ('n') (default: 'y')
- `language` (list, optional): Languages to download (default: ['ENG'])
- `link` (str, optional): Direct HUDOC search URL (default: None)
- `query_payload` (str, optional): Direct API query payload (default: None)

### `get_echr_extra`

Gets metadata and downloads full text for each case.

**Parameters:** Same as `get_echr` plus:
- `threads` (int, optional): Number of threads for parallel download (default: 10)

### `get_nodes_edges`

Generates nodes and edges for network analysis from case metadata.

**Parameters:**
- `metadata_path` (str, optional): Path to metadata CSV file (default: None)
- `df` (DataFrame, optional): Metadata DataFrame (default: None)
- `save_file` (str, optional): Save as files ('y') or return objects ('n') (default: 'y')

## Advanced Usage

### Using Custom Search URLs

You can use direct HUDOC search URLs:

```python
url = "https://hudoc.echr.coe.int/eng#{%22itemid%22:[%22001-57574%22]}"
df = get_echr(link=url)
```

### Using Query Payloads

For more robust searching, use query payloads from the browser's Network tab:

```python
payload = '{"query":{"terms":{"articles":["8"]}}}'
df = get_echr(query_payload=payload)
```

### Date Range Filtering

```python
df = get_echr(
    start_date="2020-01-01",
    end_date="2023-12-31",
    language=['ENG', 'FRE']
)
```

### Specific Fields Only

```python
fields = ['itemid', 'doctypebranch', 'title', 'kpdate']
df = get_echr(count=100, fields=fields)
```

## Requirements

- Python 3.8+
- requests
- pandas
- beautifulsoup4
- dateparser
- tqdm

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Contributors

- Benjamin Rodrigues de Miranda
- Chloe Crombach
- Piotr Lewandowski
- Pranav Bapat
- Shashank MC
- Gijs van Dijck

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

## Support

For bug reports and feature requests, please open an issue on GitHub.
