namespace EchrExtractor.Core.Models
{
    /// <summary>
    /// Represents an edge (relationship) between ECHR cases
    /// </summary>
    public class NetworkEdge
    {
        public string SourceId { get; set; } = string.Empty;
        public string TargetId { get; set; } = string.Empty;
        public string RelationType { get; set; } = string.Empty;
        public double Weight { get; set; } = 1.0;
    }
}