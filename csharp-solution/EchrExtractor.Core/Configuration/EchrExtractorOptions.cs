using System;
using System.Collections.Generic;

namespace EchrExtractor.Core.Configuration
{
    /// <summary>
    /// Configuration options for ECHR data extraction
    /// </summary>
    public class EchrExtractorOptions
    {
        public int StartId { get; set; } = 0;
        public int? EndId { get; set; }
        public int? Count { get; set; }
        public DateTime? StartDate { get; set; }
        public DateTime? EndDate { get; set; }
        public bool Verbose { get; set; } = false;
        public bool SaveFile { get; set; } = true;
        public List<string> Fields { get; set; } = new List<string>();
        public string? Link { get; set; }
        public List<string> Languages { get; set; } = new List<string> { "ENG" };
        public string? QueryPayload { get; set; }
        
        // Advanced configuration
        public int BatchSize { get; set; } = 500;
        public int TimeoutSeconds { get; set; } = 60;
        public int RetryAttempts { get; set; } = 3;
        public int MaxAttempts { get; set; } = 20;
        public int DaysPerBatch { get; set; } = 365;
        public bool ShowProgressBar { get; set; } = true;
        public bool MemoryEfficient { get; set; } = true;
        public int Threads { get; set; } = 10;
        
        public string OutputDirectory { get; set; } = "data";
    }
}