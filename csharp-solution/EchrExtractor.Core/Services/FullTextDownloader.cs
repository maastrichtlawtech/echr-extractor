using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using EchrExtractor.Core.Models;
using HtmlAgilityPack;
using Microsoft.Extensions.Logging;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// Service for downloading full text content from ECHR cases
    /// </summary>
    public class FullTextDownloader : IFullTextDownloader
    {
        private readonly IHttpService _httpService;
        private readonly ILogger<FullTextDownloader>? _logger;
        private const string BaseUrl = "https://hudoc.echr.coe.int/app/conversion/docx/html/body?library=ECHR&id=";

        public FullTextDownloader(IHttpService httpService, ILogger<FullTextDownloader>? logger = null)
        {
            _httpService = httpService ?? throw new ArgumentNullException(nameof(httpService));
            _logger = logger;
        }

        public async Task<List<EchrCase>> DownloadFullTextAsync(List<EchrCase> cases, int threads = 10, CancellationToken cancellationToken = default)
        {
            if (_logger != null)
            {
                _logger.LogInformation("Full-text download will now begin");
            }

            var semaphore = new SemaphoreSlim(threads);
            var tasks = new List<Task>();

            foreach (var echrCase in cases)
            {
                await semaphore.WaitAsync(cancellationToken);

                var task = Task.Run(async () =>
                {
                    try
                    {
                        echrCase.FullText = await DownloadSingleFullTextAsync(echrCase.ItemId, cancellationToken);
                    }
                    catch (Exception ex)
                    {
                        if (_logger != null)
                        {
                            _logger.LogWarning($"Failed to download full text for case {echrCase.ItemId}: {ex.Message}");
                        }
                        echrCase.FullText = string.Empty;
                    }
                    finally
                    {
                        semaphore.Release();
                    }
                }, cancellationToken);

                tasks.Add(task);
            }

            await Task.WhenAll(tasks);

            if (_logger != null)
            {
                _logger.LogInformation("Full-text download finished");
            }

            return cases;
        }

        private async Task<string> DownloadSingleFullTextAsync(string itemId, CancellationToken cancellationToken)
        {
            var url = $"{BaseUrl}{itemId}";
            
            try
            {
                var html = await _httpService.GetAsync(url, cancellationToken);
                return ExtractTextFromHtml(html);
            }
            catch
            {
                // Retry once on failure
                await Task.Delay(1000, cancellationToken);
                var html = await _httpService.GetAsync(url, cancellationToken);
                return ExtractTextFromHtml(html);
            }
        }

        private string ExtractTextFromHtml(string html)
        {
            var doc = new HtmlDocument();
            doc.LoadHtml(html);

            // Remove script and style elements
            var nodesToRemove = doc.DocumentNode.SelectNodes("//script|//style");
            if (nodesToRemove != null)
            {
                foreach (var node in nodesToRemove)
                {
                    node.Remove();
                }
            }

            // Get text content
            var text = doc.DocumentNode.InnerText;

            // Clean up the text
            var lines = text.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
                           .Select(line => line.Trim())
                           .Where(line => !string.IsNullOrWhiteSpace(line));

            var cleanedText = string.Join("\n", lines);
            
            // Replace commas with underscores (matching Python behavior)
            cleanedText = cleanedText.Replace(",", "_");

            return cleanedText;
        }
    }
}