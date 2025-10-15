using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using EchrExtractor.Core.Models;
using Microsoft.Extensions.Logging;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// Service for generating network analysis data from ECHR cases
    /// </summary>
    public class NetworkAnalyzer : INetworkAnalyzer
    {
        private readonly ILogger<NetworkAnalyzer>? _logger;
        private static readonly string[] CleanPatterns = { "EUR. COURT H.R.", "JUDGMENT OF.*", " DU.*" };

        public NetworkAnalyzer(ILogger<NetworkAnalyzer>? logger = null)
        {
            _logger = logger;
        }

        public (List<NetworkNode> nodes, List<NetworkEdge> edges) GenerateNodesAndEdges(List<EchrCase> cases)
        {
            var nodes = new List<NetworkNode>();
            var edges = new List<NetworkEdge>();

            // Group cases by ECLI to handle duplicates
            var groupedCases = cases.GroupBy(c => c.Ecli)
                                   .Select(g => g.First())
                                   .ToList();

            // Create nodes
            foreach (var echrCase in groupedCases)
            {
                var node = new NetworkNode
                {
                    Id = echrCase.ItemId,
                    Ecli = echrCase.Ecli,
                    AppNo = echrCase.AppNo,
                    DocName = echrCase.DocName,
                    JudgementDate = echrCase.JudgementDate,
                    Importance = echrCase.Importance,
                    LanguageIsoCode = echrCase.LanguageIsoCode
                };
                nodes.Add(node);
            }

            // Create edges based on case references
            // This is a simplified version - the full implementation would parse
            // the SCL field and other reference fields to create edges
            foreach (var echrCase in groupedCases)
            {
                if (!string.IsNullOrEmpty(echrCase.Scl))
                {
                    var references = ParseReferences(echrCase.Scl);
                    foreach (var reference in references)
                    {
                        var targetCase = groupedCases.FirstOrDefault(c => 
                            c.AppNo == reference || c.Ecli == reference);

                        if (targetCase != null)
                        {
                            var edge = new NetworkEdge
                            {
                                SourceId = echrCase.ItemId,
                                TargetId = targetCase.ItemId,
                                RelationType = "references",
                                Weight = 1.0
                            };
                            edges.Add(edge);
                        }
                    }
                }
            }

            if (_logger != null)
            {
                _logger.LogInformation($"Generated {nodes.Count} nodes and {edges.Count} edges");
            }

            return (nodes, edges);
        }

        private List<string> ParseReferences(string scl)
        {
            var references = new List<string>();

            if (string.IsNullOrEmpty(scl))
            {
                return references;
            }

            // Clean the SCL field using patterns
            var cleanedScl = scl;
            foreach (var pattern in CleanPatterns)
            {
                cleanedScl = Regex.Replace(cleanedScl, pattern, "", RegexOptions.IgnoreCase);
            }

            // Extract potential case references
            // This is a simplified version - full implementation would be more sophisticated
            var matches = Regex.Matches(cleanedScl, @"\d+/\d+");
            foreach (Match match in matches)
            {
                references.Add(match.Value);
            }

            return references.Distinct().ToList();
        }
    }
}