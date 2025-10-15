using System.Collections.Generic;
using EchrExtractor.Core.Models;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// Interface for generating network analysis data from ECHR cases
    /// </summary>
    public interface INetworkAnalyzer
    {
        (List<NetworkNode> nodes, List<NetworkEdge> edges) GenerateNodesAndEdges(List<EchrCase> cases);
    }
}