using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using EchrExtractor.Core.Configuration;
using EchrExtractor.Core.Models;

namespace EchrExtractor.Core.Services
{
    /// <summary>
    /// Interface for harvesting ECHR metadata
    /// </summary>
    public interface IMetadataHarvester
    {
        Task<List<EchrCase>> GetMetadataAsync(EchrExtractorOptions options, CancellationToken cancellationToken = default);
    }
}