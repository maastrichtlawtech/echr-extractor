using System;
using System.Collections.Generic;

namespace EchrExtractor.Core.Models
{
    /// <summary>
    /// Represents an ECHR case with metadata
    /// </summary>
    public class EchrCase
    {
        public string ItemId { get; set; } = string.Empty;
        public string AppNo { get; set; } = string.Empty;
        public string Article { get; set; } = string.Empty;
        public string Conclusion { get; set; } = string.Empty;
        public string DocName { get; set; } = string.Empty;
        public string DocType { get; set; } = string.Empty;
        public string DocTypeBranch { get; set; } = string.Empty;
        public string Ecli { get; set; } = string.Empty;
        public string Importance { get; set; } = string.Empty;
        public DateTime? JudgementDate { get; set; }
        public string LanguageIsoCode { get; set; } = string.Empty;
        public string OriginatingBody { get; set; } = string.Empty;
        public string Violation { get; set; } = string.Empty;
        public string NonViolation { get; set; } = string.Empty;
        public string ExtractedAppNo { get; set; } = string.Empty;
        public string Scl { get; set; } = string.Empty;
        public string FullText { get; set; } = string.Empty;
        
        public Dictionary<string, object> AdditionalFields { get; set; } = new Dictionary<string, object>();
    }
}