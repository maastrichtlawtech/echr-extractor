using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using CsvHelper;
using EchrExtractor.Core.Models;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// Service for exporting ECHR data to CSV and JSON formats
    /// </summary>
    public class DataExporter : IDataExporter
    {
        private readonly ILogger<DataExporter>? _logger;

        public DataExporter(ILogger<DataExporter>? logger = null)
        {
            _logger = logger;
        }

        public async Task ExportToCsvAsync(List<EchrCase> cases, string filePath)
        {
            try
            {
                EnsureDirectoryExists(filePath);

                using var writer = new StreamWriter(filePath);
                using var csv = new CsvWriter(writer, CultureInfo.InvariantCulture);
                
                await csv.WriteRecordsAsync(cases);

                if (_logger != null)
                {
                    _logger.LogInformation($"Exported {cases.Count} cases to {filePath}");
                }
            }
            catch (Exception ex)
            {
                if (_logger != null)
                {
                    _logger.LogError($"Error exporting to CSV: {ex.Message}");
                }
                throw;
            }
        }

        public async Task ExportToJsonAsync(List<EchrCase> cases, string filePath)
        {
            try
            {
                EnsureDirectoryExists(filePath);

                var json = JsonConvert.SerializeObject(cases, Formatting.Indented);
                await File.WriteAllTextAsync(filePath, json);

                if (_logger != null)
                {
                    _logger.LogInformation($"Exported {cases.Count} cases to {filePath}");
                }
            }
            catch (Exception ex)
            {
                if (_logger != null)
                {
                    _logger.LogError($"Error exporting to JSON: {ex.Message}");
                }
                throw;
            }
        }

        public async Task ExportNodesToCsvAsync(List<NetworkNode> nodes, string filePath)
        {
            try
            {
                EnsureDirectoryExists(filePath);

                using var writer = new StreamWriter(filePath);
                using var csv = new CsvWriter(writer, CultureInfo.InvariantCulture);
                
                await csv.WriteRecordsAsync(nodes);

                if (_logger != null)
                {
                    _logger.LogInformation($"Exported {nodes.Count} nodes to {filePath}");
                }
            }
            catch (Exception ex)
            {
                if (_logger != null)
                {
                    _logger.LogError($"Error exporting nodes to CSV: {ex.Message}");
                }
                throw;
            }
        }

        public async Task ExportEdgesToCsvAsync(List<NetworkEdge> edges, string filePath)
        {
            try
            {
                EnsureDirectoryExists(filePath);

                using var writer = new StreamWriter(filePath);
                using var csv = new CsvWriter(writer, CultureInfo.InvariantCulture);
                
                await csv.WriteRecordsAsync(edges);

                if (_logger != null)
                {
                    _logger.LogInformation($"Exported {edges.Count} edges to {filePath}");
                }
            }
            catch (Exception ex)
            {
                if (_logger != null)
                {
                    _logger.LogError($"Error exporting edges to CSV: {ex.Message}");
                }
                throw;
            }
        }

        public async Task ExportNodesToJsonAsync(List<NetworkNode> nodes, string filePath)
        {
            try
            {
                EnsureDirectoryExists(filePath);

                var json = JsonConvert.SerializeObject(nodes, Formatting.Indented);
                await File.WriteAllTextAsync(filePath, json);

                if (_logger != null)
                {
                    _logger.LogInformation($"Exported {nodes.Count} nodes to {filePath}");
                }
            }
            catch (Exception ex)
            {
                if (_logger != null)
                {
                    _logger.LogError($"Error exporting nodes to JSON: {ex.Message}");
                }
                throw;
            }
        }

        public async Task ExportEdgesToJsonAsync(List<NetworkEdge> edges, string filePath)
        {
            try
            {
                EnsureDirectoryExists(filePath);

                var json = JsonConvert.SerializeObject(edges, Formatting.Indented);
                await File.WriteAllTextAsync(filePath, json);

                if (_logger != null)
                {
                    _logger.LogInformation($"Exported {edges.Count} edges to {filePath}");
                }
            }
            catch (Exception ex)
            {
                if (_logger != null)
                {
                    _logger.LogError($"Error exporting edges to JSON: {ex.Message}");
                }
                throw;
            }
        }

        private void EnsureDirectoryExists(string filePath)
        {
            var directory = Path.GetDirectoryName(filePath);
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }
        }
    }
}