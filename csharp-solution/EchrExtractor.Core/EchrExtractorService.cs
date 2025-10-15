using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using EchrExtractor.Core.Configuration;
using EchrExtractor.Core.Models;
using EchrExtractor.Core.Services;
using Microsoft.Extensions.Logging;

namespace EchrExtractor.Core
{
    /// <summary>
    /// Main service for ECHR data extraction operations
    /// </summary>
    public class EchrExtractorService
    {
        private readonly IMetadataHarvester _metadataHarvester;
        private readonly IFullTextDownloader _fullTextDownloader;
        private readonly INetworkAnalyzer _networkAnalyzer;
        private readonly IDataExporter _dataExporter;
        private readonly ILogger<EchrExtractorService>? _logger;

        public EchrExtractorService(
            IMetadataHarvester metadataHarvester,
            IFullTextDownloader fullTextDownloader,
            INetworkAnalyzer networkAnalyzer,
            IDataExporter dataExporter,
            ILogger<EchrExtractorService>? logger = null)
        {
            _metadataHarvester = metadataHarvester ?? throw new ArgumentNullException(nameof(metadataHarvester));
            _fullTextDownloader = fullTextDownloader ?? throw new ArgumentNullException(nameof(fullTextDownloader));
            _networkAnalyzer = networkAnalyzer ?? throw new ArgumentNullException(nameof(networkAnalyzer));
            _dataExporter = dataExporter ?? throw new ArgumentNullException(nameof(dataExporter));
            _logger = logger;
        }

        /// <summary>
        /// Get ECHR metadata
        /// </summary>
        public async Task<List<EchrCase>> GetEchrAsync(EchrExtractorOptions options, CancellationToken cancellationToken = default)
        {
            if (_logger != null && options.Verbose)
            {
                _logger.LogInformation("--- STARTING ECHR DOWNLOAD ---");
            }

            var cases = await _metadataHarvester.GetMetadataAsync(options, cancellationToken);

            if (options.SaveFile && cases.Count > 0)
            {
                var filename = DetermineFilename(options);
                var filePath = Path.Combine(options.OutputDirectory, filename + ".csv");
                await _dataExporter.ExportToCsvAsync(cases, filePath);
            }

            if (_logger != null && options.Verbose)
            {
                _logger.LogInformation("--- DONE ---");
            }

            return cases;
        }

        /// <summary>
        /// Get ECHR metadata and full text
        /// </summary>
        public async Task<(List<EchrCase> cases, List<EchrCase> fullTextCases)> GetEchrExtraAsync(
            EchrExtractorOptions options, 
            CancellationToken cancellationToken = default)
        {
            var cases = await GetEchrAsync(options, cancellationToken);

            if (_logger != null)
            {
                _logger.LogInformation("Full-text download will now begin");
            }

            var fullTextCases = await _fullTextDownloader.DownloadFullTextAsync(cases, options.Threads, cancellationToken);

            if (options.SaveFile && fullTextCases.Count > 0)
            {
                var filename = DetermineFilename(options);
                var filenameJson = filename.Replace("metadata", "full_text");
                
                var filePath = Path.Combine(options.OutputDirectory, filename + ".csv");
                var filePathJson = Path.Combine(options.OutputDirectory, filenameJson + ".json");
                
                await _dataExporter.ExportToCsvAsync(fullTextCases, filePath);
                await _dataExporter.ExportToJsonAsync(fullTextCases, filePathJson);
            }

            return (cases, fullTextCases);
        }

        /// <summary>
        /// Generate nodes and edges for network analysis
        /// </summary>
        public async Task<(List<NetworkNode> nodes, List<NetworkEdge> edges)> GetNodesEdgesAsync(
            List<EchrCase>? cases = null,
            string? metadataPath = null,
            bool saveFile = true,
            string outputDirectory = "data")
        {
            List<EchrCase> casesToAnalyze;

            if (cases != null)
            {
                casesToAnalyze = cases;
            }
            else if (!string.IsNullOrEmpty(metadataPath))
            {
                // Load from CSV file
                casesToAnalyze = await LoadCasesFromCsvAsync(metadataPath);
            }
            else
            {
                throw new ArgumentException("Either cases or metadataPath must be provided");
            }

            var (nodes, edges) = _networkAnalyzer.GenerateNodesAndEdges(casesToAnalyze);

            if (saveFile)
            {
                var nodesPath = Path.Combine(outputDirectory, "ECHR_nodes.csv");
                var edgesPath = Path.Combine(outputDirectory, "ECHR_edges.csv");
                var nodesJsonPath = Path.Combine(outputDirectory, "ECHR_nodes.json");
                var edgesJsonPath = Path.Combine(outputDirectory, "ECHR_edges.json");

                await _dataExporter.ExportNodesToCsvAsync(nodes, nodesPath);
                await _dataExporter.ExportEdgesToCsvAsync(edges, edgesPath);
                await _dataExporter.ExportNodesToJsonAsync(nodes, nodesJsonPath);
                await _dataExporter.ExportEdgesToJsonAsync(edges, edgesJsonPath);
            }

            return (nodes, edges);
        }

        private string DetermineFilename(EchrExtractorOptions options)
        {
            var startId = options.StartId;
            var endId = options.EndId?.ToString() ?? "ALL";
            var startDate = options.StartDate?.ToString("yyyy-MM-dd") ?? "START";
            var endDate = options.EndDate?.ToString("yyyy-MM-dd") ?? "END";

            return $"echr_metadata_{startId}-{endId}_dates_{startDate}-{endDate}";
        }

        private async Task<List<EchrCase>> LoadCasesFromCsvAsync(string filePath)
        {
            // This is a placeholder - implement CSV reading logic
            // For now, return empty list
            await Task.CompletedTask;
            return new List<EchrCase>();
        }
    }
}