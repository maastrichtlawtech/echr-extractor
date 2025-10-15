using System;
using System.Threading;
using System.Threading.Tasks;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// Interface for HTTP operations with retry logic
    /// </summary>
    public interface IHttpService
    {
        Task<string> GetAsync(string url, CancellationToken cancellationToken = default);
        Task<string> GetWithRetryAsync(string url, int maxAttempts, int timeoutSeconds, CancellationToken cancellationToken = default);
    }
}