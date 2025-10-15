# ECHR Extractor - C# .NET Implementation

C# .NET implementation of the ECHR Extractor library for extracting case law data from the European Court of Human Rights (ECHR) HUDOC database.

## Overview

This is a C# .NET port of the original Python ECHR Extractor library. It provides the same functionality for extracting metadata, full text content, and generating network analysis data from ECHR cases.

## Features

- Extract metadata for ECHR cases from the HUDOC database
- Download full text content for cases
- Support for custom date ranges and case ID ranges
- Multiple language support
- Generate nodes and edges for network analysis
- Flexible output formats (CSV, JSON)
- Asynchronous operations with configurable parallelism
- Comprehensive error handling and retry logic

## Project Structure

```
csharp-solution/
├── EchrExtractor.sln                 # Solution file
├── EchrExtractor.Core/               # Core library
│   ├── Models/                       # Data models
│   │   ├── EchrCase.cs              # ECHR case model
│   │   ├── NetworkNode.cs           # Network node model
│   │   └── NetworkEdge.cs           # Network edge model
│   ├── Configuration/                # Configuration classes
│   │   └── EchrExtractorOptions.cs  # Extraction options
│   ├── Services/                     # Service implementations
│   │   ├── HttpService.cs           # HTTP operations with retry
│   │   ├── MetadataHarvester.cs     # Metadata extraction
│   │   ├── FullTextDownloader.cs    # Full text download
│   │   ├── NetworkAnalyzer.cs       # Network analysis
│   │   └── DataExporter.cs          # Data export (CSV/JSON)
│   └── EchrExtractorService.cs      # Main service facade
└── EchrExtractor.CLI/                # Command-line interface
    └── Program.cs                    # CLI entry point
```

## Requirements

- .NET 8.0 SDK or later
- Visual Studio 2022 or later (recommended) or any .NET-compatible IDE

## Installation

### Building from Source

1. Clone the repository:
```bash
git clone https://github.com/leventtumen/echr-extractor.git
cd echr-extractor/csharp-solution
```

2. Build the solution:
```bash
dotnet build
```

3. Run the CLI:
```bash
dotnet run --project EchrExtractor.CLI -- help
```

### Using in Visual Studio

1. Open `EchrExtractor.sln` in Visual Studio 2022
2. Build the solution (Ctrl+Shift+B)
3. Set `EchrExtractor.CLI` as the startup project
4. Run or debug the application (F5)

## Usage

### Command Line Interface

The CLI provides three main commands:

#### 1. Extract Metadata

Extract basic metadata for ECHR cases:

```bash
dotnet run --project EchrExtractor.CLI -- extract --count 100 --verbose
```

Options:
- `--start-id <number>`: ID of first case to download (default: 0)
- `--end-id <number>`: ID of last case to download
- `--count <number>`: Number of cases per language to download
- `--start-date <date>`: Start publication date (yyyy-MM-dd)
- `--end-date <date>`: End publication date (yyyy-MM-dd)
- `--verbose`: Show progress information
- `--no-save`: Don't save files, return objects only
- `--language <lang>`: Languages to download (default: ENG)

#### 2. Extract Metadata + Full Text

Extract metadata and download full text content:

```bash
dotnet run --project EchrExtractor.CLI -- extract-full --start-id 0 --count 50 --threads 10 --verbose
```

Additional options:
- `--threads <number>`: Number of threads for parallel download (default: 10)

#### 3. Generate Network Data

Generate nodes and edges for network analysis:

```bash
dotnet run --project EchrExtractor.CLI -- network --metadata-path data/metadata.csv
```

Options:
- `--metadata-path <path>`: Path to metadata CSV file
- `--no-save`: Don't save files, return objects only

### Using as a Library

You can also use the library programmatically in your C# projects:

```csharp
using EchrExtractor.Core;
using EchrExtractor.Core.Configuration;
using EchrExtractor.Core.Services;
using Microsoft.Extensions.DependencyInjection;

// Set up dependency injection
var services = new ServiceCollection();
services.AddHttpClient<IHttpService, HttpService>();
services.AddSingleton<IMetadataHarvester, MetadataHarvester>();
services.AddSingleton<IFullTextDownloader, FullTextDownloader>();
services.AddSingleton<INetworkAnalyzer, NetworkAnalyzer>();
services.AddSingleton<IDataExporter, DataExporter>();
services.AddSingleton<EchrExtractorService>();

var serviceProvider = services.BuildServiceProvider();
var extractorService = serviceProvider.GetRequiredService<EchrExtractorService>();

// Configure extraction options
var options = new EchrExtractorOptions
{
    StartId = 0,
    Count = 100,
    Languages = new List<string> { "ENG" },
    Verbose = true,
    SaveFile = true
};

// Extract metadata
var cases = await extractorService.GetEchrAsync(options);
Console.WriteLine($"Extracted {cases.Count} cases");

// Extract metadata + full text
var (metadata, fullText) = await extractorService.GetEchrExtraAsync(options);

// Generate network data
var (nodes, edges) = await extractorService.GetNodesEdgesAsync(cases: cases);
```

## NuGet Packages Used

- **Newtonsoft.Json** (13.0.4): JSON serialization/deserialization
- **HtmlAgilityPack** (1.12.4): HTML parsing for full text extraction
- **CsvHelper** (33.1.0): CSV file reading/writing
- **Microsoft.Extensions.Logging** (9.0.10): Logging infrastructure
- **Microsoft.Extensions.DependencyInjection** (9.0.10): Dependency injection
- **Microsoft.Extensions.Http** (9.0.10): HTTP client factory

## Output Files

The extractor creates the following files in the `data/` directory:

- `echr_metadata_<range>_dates_<dates>.csv`: Metadata in CSV format
- `echr_full_text_<range>_dates_<dates>.json`: Full text content in JSON format
- `ECHR_nodes.csv` / `ECHR_nodes.json`: Network nodes
- `ECHR_edges.csv` / `ECHR_edges.json`: Network edges

## Comparison with Python Version

### Similarities
- Same core functionality and API design
- Compatible output formats
- Similar configuration options
- Equivalent error handling and retry logic

### Differences
- **Performance**: C# version may offer better performance for CPU-intensive operations
- **Type Safety**: Strong typing in C# provides compile-time safety
- **Async/Await**: Native async support throughout the codebase
- **Dependency Injection**: Built-in DI container for better testability
- **IDE Support**: Better IntelliSense and refactoring tools in Visual Studio

## Development

### Running Tests

```bash
dotnet test
```

### Building Release Version

```bash
dotnet build -c Release
```

### Publishing

```bash
dotnet publish -c Release -o ./publish
```

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Authors

- **Original Python Version**: LawTech Lab, Maastricht University
- **C# Port**: Levent Tumen

## Acknowledgments

- Original Python ECHR Extractor: https://github.com/maastrichtlawtech/echr-extractor
- European Court of Human Rights HUDOC database: https://hudoc.echr.coe.int/

## Support

For bug reports and feature requests, please open an issue on GitHub.