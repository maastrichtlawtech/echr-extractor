using System;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;
using EchrExtractor.Core;
using EchrExtractor.Core.Configuration;
using EchrExtractor.Core.Services;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace EchrExtractor.CLI
{
    class Program
    {
        static async Task<int> Main(string[] args)
        {
            if (args.Length == 0)
            {
                PrintHelp();
                return 0;
            }

            var command = args[0].ToLower();

            try
            {
                switch (command)
                {
                    case "extract":
                        await ExecuteExtractAsync(args.Skip(1).ToArray());
                        break;
                    case "extract-full":
                        await ExecuteExtractFullAsync(args.Skip(1).ToArray());
                        break;
                    case "network":
                        await ExecuteNetworkAsync(args.Skip(1).ToArray());
                        break;
                    case "help":
                    case "--help":
                    case "-h":
                        PrintHelp();
                        break;
                    default:
                        Console.WriteLine($"Unknown command: {command}");
                        PrintHelp();
                        return 1;
                }

                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Error: {ex.Message}");
                return 1;
            }
        }

        static void PrintHelp()
        {
            Console.WriteLine("ECHR Extractor - Extract case law data from the European Court of Human Rights (ECHR) HUDOC database");
            Console.WriteLine();
            Console.WriteLine("Usage: echr-extractor <command> [options]");
            Console.WriteLine();
            Console.WriteLine("Commands:");
            Console.WriteLine("  extract       Extract ECHR metadata");
            Console.WriteLine("  extract-full  Extract ECHR metadata and full text");
            Console.WriteLine("  network       Generate nodes and edges for network analysis");
            Console.WriteLine("  help          Show this help message");
            Console.WriteLine();
            Console.WriteLine("Common Options:");
            Console.WriteLine("  --start-id <number>      ID of first case to download (default: 0)");
            Console.WriteLine("  --end-id <number>        ID of last case to download");
            Console.WriteLine("  --count <number>         Number of cases per language to download");
            Console.WriteLine("  --start-date <date>      Start publication date (yyyy-MM-dd)");
            Console.WriteLine("  --end-date <date>        End publication date (yyyy-MM-dd)");
            Console.WriteLine("  --verbose                Show progress information");
            Console.WriteLine("  --no-save                Don't save files, return objects only");
            Console.WriteLine("  --language <lang>        Languages to download (default: ENG)");
            Console.WriteLine();
            Console.WriteLine("Extract-Full Options:");
            Console.WriteLine("  --threads <number>       Number of threads for parallel download (default: 10)");
            Console.WriteLine();
            Console.WriteLine("Network Options:");
            Console.WriteLine("  --metadata-path <path>   Path to metadata CSV file");
            Console.WriteLine();
            Console.WriteLine("Examples:");
            Console.WriteLine("  echr-extractor extract --count 100 --verbose");
            Console.WriteLine("  echr-extractor extract-full --start-id 0 --count 50 --threads 5");
            Console.WriteLine("  echr-extractor network --metadata-path data/metadata.csv");
        }

        static EchrExtractorOptions ParseOptions(string[] args)
        {
            var options = new EchrExtractorOptions();

            for (int i = 0; i < args.Length; i++)
            {
                switch (args[i].ToLower())
                {
                    case "--start-id":
                        if (i + 1 < args.Length && int.TryParse(args[++i], out var startId))
                            options.StartId = startId;
                        break;
                    case "--end-id":
                        if (i + 1 < args.Length && int.TryParse(args[++i], out var endId))
                            options.EndId = endId;
                        break;
                    case "--count":
                        if (i + 1 < args.Length && int.TryParse(args[++i], out var count))
                            options.Count = count;
                        break;
                    case "--start-date":
                        if (i + 1 < args.Length && DateTime.TryParse(args[++i], out var startDate))
                            options.StartDate = startDate;
                        break;
                    case "--end-date":
                        if (i + 1 < args.Length && DateTime.TryParse(args[++i], out var endDate))
                            options.EndDate = endDate;
                        break;
                    case "--verbose":
                        options.Verbose = true;
                        break;
                    case "--no-save":
                        options.SaveFile = false;
                        break;
                    case "--language":
                        if (i + 1 < args.Length)
                        {
                            options.Languages.Clear();
                            options.Languages.Add(args[++i]);
                        }
                        break;
                    case "--threads":
                        if (i + 1 < args.Length && int.TryParse(args[++i], out var threads))
                            options.Threads = threads;
                        break;
                }
            }

            return options;
        }

        static async Task ExecuteExtractAsync(string[] args)
        {
            var options = ParseOptions(args);
            var serviceProvider = BuildServiceProvider(options.Verbose);
            var extractorService = serviceProvider.GetRequiredService<EchrExtractorService>();

            var cases = await extractorService.GetEchrAsync(options);
            Console.WriteLine($"Extracted {cases.Count} cases");
        }

        static async Task ExecuteExtractFullAsync(string[] args)
        {
            var options = ParseOptions(args);
            var serviceProvider = BuildServiceProvider(options.Verbose);
            var extractorService = serviceProvider.GetRequiredService<EchrExtractorService>();

            var (cases, fullTextCases) = await extractorService.GetEchrExtraAsync(options);
            Console.WriteLine($"Extracted {cases.Count} cases with full text");
        }

        static async Task ExecuteNetworkAsync(string[] args)
        {
            string? metadataPath = null;
            bool saveFile = true;

            for (int i = 0; i < args.Length; i++)
            {
                switch (args[i].ToLower())
                {
                    case "--metadata-path":
                        if (i + 1 < args.Length)
                            metadataPath = args[++i];
                        break;
                    case "--no-save":
                        saveFile = false;
                        break;
                }
            }

            var serviceProvider = BuildServiceProvider(false);
            var extractorService = serviceProvider.GetRequiredService<EchrExtractorService>();

            var (nodes, edges) = await extractorService.GetNodesEdgesAsync(
                metadataPath: metadataPath,
                saveFile: saveFile);
            Console.WriteLine($"Generated {nodes.Count} nodes and {edges.Count} edges");
        }

        static ServiceProvider BuildServiceProvider(bool verbose)
        {
            var services = new ServiceCollection();

            // Add logging
            services.AddLogging(builder =>
            {
                builder.AddConsole();
                if (verbose)
                {
                    builder.SetMinimumLevel(LogLevel.Information);
                }
                else
                {
                    builder.SetMinimumLevel(LogLevel.Warning);
                }
            });

            // Add HttpClient
            services.AddHttpClient<IHttpService, HttpService>();

            // Add services
            services.AddSingleton<IMetadataHarvester, MetadataHarvester>();
            services.AddSingleton<IFullTextDownloader, FullTextDownloader>();
            services.AddSingleton<INetworkAnalyzer, NetworkAnalyzer>();
            services.AddSingleton<IDataExporter, DataExporter>();
            services.AddSingleton<EchrExtractorService>();

            return services.BuildServiceProvider();
        }
    }
}