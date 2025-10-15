using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using EchrExtractor.Core.Models;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// Interface for downloading full text content of ECHR cases
    /// </summary>
    public interface IFullTextDownloader
    {
        Task<List<EchrCase>> DownloadFullTextAsync(List<EchrCase> cases, int threads = 10, CancellationToken cancellationToken = default);
    }
}