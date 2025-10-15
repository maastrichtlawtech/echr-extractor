using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using EchrExtractor.Core.Configuration;
using EchrExtractor.Core.Models;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// Service for harvesting ECHR case metadata from HUDOC database
    /// </summary>
    public class MetadataHarvester : IMetadataHarvester
    {
        private readonly IHttpService _httpService;
        private readonly ILogger<MetadataHarvester>? _logger;
        private const string BaseApiUrl = "https://hudoc.echr.coe.int/app/query/results";

        public MetadataHarvester(IHttpService httpService, ILogger<MetadataHarvester>? logger = null)
        {
            _httpService = httpService ?? throw new ArgumentNullException(nameof(httpService));
            _logger = logger;
        }

        public async Task<List<EchrCase>> GetMetadataAsync(EchrExtractorOptions options, CancellationToken cancellationToken = default)
        {
            var allCases = new List<EchrCase>();
            
            if (_logger != null && options.Verbose)
            {
                _logger.LogInformation("--- STARTING ECHR METADATA DOWNLOAD ---");
            }

            // Determine date ranges for batching
            var dateRanges = GetDateRanges(options.StartDate, options.EndDate, options.DaysPerBatch);

            foreach (var (startDate, endDate) in dateRanges)
            {
                var batchCases = await FetchBatchAsync(options, startDate, endDate, cancellationToken);
                allCases.AddRange(batchCases);

                if (_logger != null && options.Verbose)
                {
                    _logger.LogInformation($"Fetched {batchCases.Count} cases for date range {startDate} to {endDate}");
                }
            }

            if (_logger != null && options.Verbose)
            {
                _logger.LogInformation($"Total cases fetched: {allCases.Count}");
            }

            return allCases;
        }

        private async Task<List<EchrCase>> FetchBatchAsync(
            EchrExtractorOptions options, 
            DateTime? startDate, 
            DateTime? endDate, 
            CancellationToken cancellationToken)
        {
            var cases = new List<EchrCase>();
            int offset = options.StartId;
            bool hasMore = true;

            while (hasMore && (options.EndId == null || offset < options.EndId))
            {
                var url = BuildQueryUrl(options, offset, startDate, endDate);
                
                try
                {
                    var jsonResponse = await _httpService.GetWithRetryAsync(
                        url, 
                        options.MaxAttempts, 
                        options.TimeoutSeconds, 
                        cancellationToken);

                    var batchCases = ParseJsonResponse(jsonResponse);
                    cases.AddRange(batchCases);

                    if (batchCases.Count < options.BatchSize)
                    {
                        hasMore = false;
                    }
                    else
                    {
                        offset += options.BatchSize;
                    }

                    if (options.Count.HasValue && cases.Count >= options.Count.Value)
                    {
                        cases = cases.Take(options.Count.Value).ToList();
                        hasMore = false;
                    }
                }
                catch (Exception ex)
                {
                    if (_logger != null)
                    {
                        _logger.LogError($"Error fetching batch at offset {offset}: {ex.Message}");
                    }
                    hasMore = false;
                }
            }

            return cases;
        }

        private string BuildQueryUrl(EchrExtractorOptions options, int offset, DateTime? startDate, DateTime? endDate)
        {
            var queryParams = new Dictionary<string, string>
            {
                ["query"] = BuildQuery(options, startDate, endDate),
                ["select"] = string.Join(",", GetFieldsList(options.Fields)),
                ["sort"] = "itemid Ascending",
                ["start"] = offset.ToString(),
                ["length"] = options.BatchSize.ToString()
            };

            var queryString = string.Join("&", queryParams.Select(kvp => $"{kvp.Key}={Uri.EscapeDataString(kvp.Value)}"));
            return $"{BaseApiUrl}?{queryString}";
        }

        private string BuildQuery(EchrExtractorOptions options, DateTime? startDate, DateTime? endDate)
        {
            var queryParts = new List<string>();

            // Language filter
            if (options.Languages.Any())
            {
                var langQuery = string.Join(" OR ", options.Languages.Select(lang => $"(languageisocode:&quot;{lang}&quot;)"));
                queryParts.Add($"({langQuery})");
            }

            // Date range filter
            if (startDate.HasValue || endDate.HasValue)
            {
                var start = startDate?.ToString("yyyy-MM-dd") ?? "*";
                var end = endDate?.ToString("yyyy-MM-dd") ?? "*";
                queryParts.Add($"(kpdate:[{start} TO {end}])");
            }

            // Custom query payload
            if (!string.IsNullOrEmpty(options.QueryPayload))
            {
                queryParts.Add($"({options.QueryPayload})");
            }

            return queryParts.Any() ? string.Join(" AND ", queryParts) : "*";
        }

        private List<string> GetFieldsList(List<string> customFields)
        {
            if (customFields != null && customFields.Any())
            {
                return customFields;
            }

            return new List<string>
            {
                "itemid", "appno", "article", "conclusion", "docname", "doctype",
                "doctypebranch", "ecli", "importance", "judgementdate", "languageisocode",
                "originatingbody", "violation", "nonviolation", "extractedappno", "scl"
            };
        }

        private List<EchrCase> ParseJsonResponse(string jsonResponse)
        {
            var cases = new List<EchrCase>();

            try
            {
                var json = JObject.Parse(jsonResponse);
                var results = json["results"]?.ToObject<JArray>();

                if (results != null)
                {
                    foreach (var result in results)
                    {
                        var echrCase = new EchrCase
                        {
                            ItemId = result["itemid"]?.ToString() ?? string.Empty,
                            AppNo = result["appno"]?.ToString() ?? string.Empty,
                            Article = result["article"]?.ToString() ?? string.Empty,
                            Conclusion = result["conclusion"]?.ToString() ?? string.Empty,
                            DocName = result["docname"]?.ToString() ?? string.Empty,
                            DocType = result["doctype"]?.ToString() ?? string.Empty,
                            DocTypeBranch = result["doctypebranch"]?.ToString() ?? string.Empty,
                            Ecli = result["ecli"]?.ToString() ?? string.Empty,
                            Importance = result["importance"]?.ToString() ?? string.Empty,
                            LanguageIsoCode = result["languageisocode"]?.ToString() ?? string.Empty,
                            OriginatingBody = result["originatingbody"]?.ToString() ?? string.Empty,
                            Violation = result["violation"]?.ToString() ?? string.Empty,
                            NonViolation = result["nonviolation"]?.ToString() ?? string.Empty,
                            ExtractedAppNo = result["extractedappno"]?.ToString() ?? string.Empty,
                            Scl = result["scl"]?.ToString() ?? string.Empty
                        };

                        // Parse judgement date
                        if (DateTime.TryParse(result["judgementdate"]?.ToString(), out var judgementDate))
                        {
                            echrCase.JudgementDate = judgementDate;
                        }

                        cases.Add(echrCase);
                    }
                }
            }
            catch (Exception ex)
            {
                if (_logger != null)
                {
                    _logger.LogError($"Error parsing JSON response: {ex.Message}");
                }
            }

            return cases;
        }

        private List<(DateTime?, DateTime?)> GetDateRanges(DateTime? startDate, DateTime? endDate, int daysPerBatch)
        {
            if (!startDate.HasValue || !endDate.HasValue)
            {
                return new List<(DateTime?, DateTime?)> { (startDate, endDate) };
            }

            var ranges = new List<(DateTime?, DateTime?)>();
            var currentStart = startDate.Value;

            while (currentStart < endDate.Value)
            {
                var currentEnd = currentStart.AddDays(daysPerBatch - 1);
                if (currentEnd > endDate.Value)
                {
                    currentEnd = endDate.Value;
                }

                ranges.Add((currentStart, currentEnd));
                currentStart = currentEnd.AddDays(1);
            }

            return ranges;
        }
    }
}