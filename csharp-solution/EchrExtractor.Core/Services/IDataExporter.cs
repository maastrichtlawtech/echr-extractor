using System.Collections.Generic;
using System.Threading.Tasks;
using EchrExtractor.Core.Models;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// Interface for exporting ECHR data to various formats
    /// </summary>
    public interface IDataExporter
    {
        Task ExportToCsvAsync(List<EchrCase> cases, string filePath);
        Task ExportToJsonAsync(List<EchrCase> cases, string filePath);
        Task ExportNodesToCsvAsync(List<NetworkNode> nodes, string filePath);
        Task ExportEdgesToCsvAsync(List<NetworkEdge> edges, string filePath);
        Task ExportNodesToJsonAsync(List<NetworkNode> nodes, string filePath);
        Task ExportEdgesToJsonAsync(List<NetworkEdge> edges, string filePath);
    }
}