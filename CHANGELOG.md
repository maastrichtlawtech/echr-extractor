# Changelog

All notable changes to the ECHR Extractor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-09-12

### Added

- Date range batching for large datasets to prevent API timeouts
- Enhanced error handling with exponential backoff retry logic
- Progress tracking with tqdm progress bars for long-running operations
- Memory management with chunked processing for large datasets
- Configurable batch sizes, timeouts, and retry parameters
- Comprehensive docstrings and usage examples for all functions
- New parameters: `batch_size`, `timeout`, `retry_attempts`, `max_attempts`, `days_per_batch`, `progress_bar`, `memory_efficient`

### Changed

- Enhanced `get_r()` function with better error handling and exponential backoff
- Completely rewritten `get_echr_metadata()` with batching and memory management
- Updated `get_echr()` and `get_echr_extra()` functions with new configuration parameters
- Improved logging and status reporting throughout the extraction process
- Better handling of large date ranges by splitting them into manageable chunks

### Fixed

- Memory issues when processing very large datasets
- API timeout issues for multi-year date range extractions
- Better error recovery and retry mechanisms
- Improved handling of network failures and connection errors

### Performance

- Significantly improved reliability for large-scale data extraction
- Reduced memory usage through intelligent chunked processing
- Better progress visibility for long-running operations
- More robust handling of network interruptions

## [1.0.44] - 2025-07-02

### Added

- Initial release as standalone package
- Migrated from maastrichtlawtech/extraction_libraries echr branch
- Modern Python package structure with pyproject.toml
- Command-line interface (CLI) support
- Comprehensive documentation and examples
- CI/CD pipeline with GitHub Actions
- Development tools setup (black, isort, flake8, pytest)

### Changed

- Restructured as proper Python package with src/ layout
- Updated import statements for relative imports
- Improved package metadata and dependencies
- Enhanced README with comprehensive usage examples

### Fixed

- Import paths for proper package distribution
- Package structure for PyPI publishing
- Dependencies and requirements specifications

## Previous Versions

This package was previously part of the extraction_libraries repository
under the 'echr' branch. For historical changes, please refer to:
https://github.com/maastrichtlawtech/extraction_libraries/tree/echr
