using System;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// HTTP service with retry logic and exponential backoff
    /// </summary>
    public class HttpService : IHttpService
    {
        private readonly HttpClient _httpClient;
        private readonly ILogger<HttpService>? _logger;

        public HttpService(HttpClient httpClient, ILogger<HttpService>? logger = null)
        {
            _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
            _logger = logger;
        }

        public async Task<string> GetAsync(string url, CancellationToken cancellationToken = default)
        {
            var response = await _httpClient.GetAsync(url, cancellationToken);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadAsStringAsync(cancellationToken);
        }

        public async Task<string> GetWithRetryAsync(string url, int maxAttempts, int timeoutSeconds, CancellationToken cancellationToken = default)
        {
            int attempt = 0;
            Exception? lastException = null;

            while (attempt < maxAttempts)
            {
                try
                {
                    using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                    cts.CancelAfter(TimeSpan.FromSeconds(timeoutSeconds));

                    var response = await _httpClient.GetAsync(url, cts.Token);
                    response.EnsureSuccessStatusCode();
                    return await response.Content.ReadAsStringAsync(cts.Token);
                }
                catch (Exception ex) when (ex is HttpRequestException || ex is TaskCanceledException || ex is OperationCanceledException)
                {
                    lastException = ex;
                    attempt++;

                    if (_logger != null)
                    {
                        _logger.LogWarning($"Request failed (attempt {attempt}/{maxAttempts}): {ex.GetType().Name}: {ex.Message}");
                    }

                    if (attempt < maxAttempts)
                    {
                        // Exponential backoff, capped at 30 seconds
                        var waitTime = Math.Min(Math.Pow(2, attempt), 30);
                        
                        if (_logger != null)
                        {
                            _logger.LogInformation($"Retrying in {waitTime} seconds...");
                        }

                        await Task.Delay(TimeSpan.FromSeconds(waitTime), cancellationToken);
                    }
                }
            }

            var errorMessage = $"Max attempts ({maxAttempts}) exceeded for {url}. Last error: {lastException?.Message}";
            if (_logger != null)
            {
                _logger.LogError(errorMessage);
            }
            
            throw new HttpRequestException(errorMessage, lastException);
        }
    }
}