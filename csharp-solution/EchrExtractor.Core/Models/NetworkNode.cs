using System;

namespace EchrExtractor.Core.Models
{
    /// <summary>
    /// Represents a node in the ECHR case network
    /// </summary>
    public class NetworkNode
    {
        public string Id { get; set; } = string.Empty;
        public string Ecli { get; set; } = string.Empty;
        public string AppNo { get; set; } = string.Empty;
        public string DocName { get; set; } = string.Empty;
        public DateTime? JudgementDate { get; set; }
        public string Importance { get; set; } = string.Empty;
        public string LanguageIsoCode { get; set; } = string.Empty;
    }
}