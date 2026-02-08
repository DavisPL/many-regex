using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using Resharp;
using DotnetRegex = System.Text.RegularExpressions.Regex;

class Program
{
    private const int DefaultInputSize = 50;
    private const int DefaultRuns = 3;
    private static readonly TimeSpan DefaultTimeout = TimeSpan.FromSeconds(2);

    static void Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--child")
        {
            RunChild(args);
            return;
        }

        var inputSize = ParseIntArg(args, "--input-length", ParseIntArg(args, "--input-size", DefaultInputSize));
        var numRuns = ParseIntArg(args, "--runs", DefaultRuns);
        var timeoutSeconds = ParseDoubleArg(args, "--timeout", DefaultTimeout.TotalSeconds);
        if (timeoutSeconds <= 0)
        {
            throw new ArgumentException($"Invalid value for --timeout: {timeoutSeconds.ToString(CultureInfo.InvariantCulture)}");
        }
        var timeout = TimeSpan.FromSeconds(timeoutSeconds);
        var singleTestId = ParseNullableIntArg(args, "--single");
        var showTests = HasFlag(args, "--show-tests");

        var libraries = GetLibraries(timeout);
        var tests = GetTestCases(inputSize);

        if (singleTestId.HasValue)
        {
            var results = RunSingleTest(singleTestId.Value, libraries, tests);
            foreach (var result in results)
            {
                Console.WriteLine($"{result.Library}: {result.Result.Result}");
            }
            return;
        }

        var allResults = RunAllTests(numRuns, libraries, tests, showTests);
        var summaryStats = CalculateSummaryStats(allResults, libraries);
        SaveResults(allResults, summaryStats, libraries, numRuns, tests.Count, timeoutSeconds);
    }

    static void RunChild(string[] args)
    {
        if (args.Length < 5)
        {
            WriteChildResult(new ChildResult { Error = "Child invocation requires engine, pattern, input, and testId." });
            return;
        }

        var engine = args[1];
        var pattern = args[2];
        var input = args[3];

        try
        {
            if (engine == "RE#")
            {
                var match = new Regex(pattern).IsMatch(input);
                WriteChildResult(new ChildResult { Match = match });
                return;
            }

            if (engine == "dotnet")
            {
                var match = new DotnetRegex(pattern).IsMatch(input);
                WriteChildResult(new ChildResult { Match = match });
                return;
            }

            WriteChildResult(new ChildResult { Error = $"Unknown engine: {engine}" });
        }
        catch (Exception ex)
        {
            WriteChildResult(new ChildResult { Error = $"{ex.GetType().Name}: {ex.Message}" });
        }
    }

    static void WriteChildResult(ChildResult result)
    {
        var options = new JsonSerializerOptions
        {
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
        };
        Console.WriteLine(JsonSerializer.Serialize(result, options));
    }

    static List<RegexLibrary> GetLibraries(TimeSpan timeout)
    {
        return new List<RegexLibrary>
        {
            new RegexLibrary { Name = "RE#", Engine = "RE#", Timeout = timeout },
            new RegexLibrary { Name = "dotnet", Engine = "dotnet", Timeout = timeout },
        };
    }

    static List<TestCaseRun> GetTestCases(int inputSize)
    {
        var testCasesPath = FindFilePath("test_cases.json");
        if (string.IsNullOrWhiteSpace(testCasesPath))
        {
            throw new FileNotFoundException("Unable to locate test_cases.json.");
        }

        var raw = File.ReadAllText(testCasesPath);
        var testCases = JsonSerializer.Deserialize<List<TestCase>>(
            raw,
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true }
        );

        if (testCases == null)
        {
            throw new InvalidOperationException("Failed to parse test_cases.json.");
        }

        return testCases
            .OrderBy(tc => tc.Id)
            .Select(tc => new TestCaseRun
            {
                Id = tc.Id,
                Pattern = tc.Regex,
                Input = RepeatString(tc.Repeat, inputSize)
            })
            .ToList();
    }

    static List<SingleTestResult> RunSingleTest(
        int testId,
        List<RegexLibrary> libraries,
        List<TestCaseRun> tests
    )
    {
        if (testId < 1 || testId > tests.Count)
        {
            throw new ArgumentOutOfRangeException(nameof(testId), $"Invalid test_id. Must be between 1 and {tests.Count}.");
        }

        var test = tests[testId - 1];
        var results = new List<SingleTestResult>();

        foreach (var library in libraries)
        {
            results.Add(RunTestWithTimeout(library, test.Id, test.Pattern, test.Input));
        }

        return results;
    }

    static List<SingleTestResult> RunAllTests(
        int numRuns,
        List<RegexLibrary> libraries,
        List<TestCaseRun> tests,
        bool showTests
    )
    {
        var allResults = new List<SingleTestResult>();

        for (var run = 0; run < numRuns; run++)
        {
            Console.WriteLine($"Run {run + 1}/{numRuns}");
            foreach (var test in tests)
            {
                if (showTests)
                {
                    Console.WriteLine($"  Test {test.Id}");
                }

                foreach (var library in libraries)
                {
                    allResults.Add(RunTestWithTimeout(library, test.Id, test.Pattern, test.Input));
                }
            }
        }

        return allResults;
    }

    static SingleTestResult RunTestWithTimeout(
        RegexLibrary library,
        int testId,
        string pattern,
        string input
    )
    {
        var startInfo = CreateChildProcessStartInfo(library.Engine, pattern, input, testId);
        using var process = Process.Start(startInfo);
        var stopwatch = Stopwatch.StartNew();

        if (process == null)
        {
            stopwatch.Stop();
            return BuildResult(testId, pattern, input, library.Name, null, stopwatch.Elapsed.TotalSeconds, timedOut: false);
        }

        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();

        if (!process.WaitForExit((int)library.Timeout.TotalMilliseconds))
        {
            TryKillProcessTree(process);
            stopwatch.Stop();
            return BuildResult(testId, pattern, input, library.Name, null, stopwatch.Elapsed.TotalSeconds, timedOut: true);
        }

        stopwatch.Stop();
        var stdout = stdoutTask.Result;
        var stderr = stderrTask.Result;
        var childResult = ParseChildResult(stdout, stderr);

        return BuildResult(
            testId,
            pattern,
            input,
            library.Name,
            childResult.Match,
            stopwatch.Elapsed.TotalSeconds,
            timedOut: false
        );
    }

    static ChildResult ParseChildResult(string stdout, string stderr)
    {
        if (!string.IsNullOrWhiteSpace(stderr))
        {
            return new ChildResult { Error = stderr.Trim() };
        }

        if (string.IsNullOrWhiteSpace(stdout))
        {
            return new ChildResult { Error = "Empty child output." };
        }

        try
        {
            var result = JsonSerializer.Deserialize<ChildResult>(
                stdout,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true }
            );
            return result ?? new ChildResult { Error = "Failed to parse child output." };
        }
        catch (Exception ex)
        {
            return new ChildResult { Error = $"Failed to parse child output: {ex.Message}" };
        }
    }

    static SingleTestResult BuildResult(
        int testId,
        string pattern,
        string input,
        string libraryName,
        bool? match,
        double elapsedSeconds,
        bool timedOut
    )
    {
        return new SingleTestResult
        {
            TestId = testId,
            Pattern = pattern,
            Input = input,
            Library = libraryName,
            Result = new LibraryResult
            {
                Library = libraryName,
                Result = match,
                Time = elapsedSeconds,
                TimedOut = timedOut
            }
        };
    }

    static ProcessStartInfo CreateChildProcessStartInfo(
        string engine,
        string pattern,
        string input,
        int testId
    )
    {
        var processPath = Environment.ProcessPath;
        var assemblyPath = Assembly.GetExecutingAssembly().Location;

        if (string.IsNullOrWhiteSpace(processPath))
        {
            throw new InvalidOperationException("Unable to determine current process path.");
        }

        var startInfo = new ProcessStartInfo
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };

        if (Path.GetFileName(processPath).Equals("dotnet", StringComparison.OrdinalIgnoreCase)
            && !string.IsNullOrWhiteSpace(assemblyPath))
        {
            startInfo.FileName = processPath;
            startInfo.ArgumentList.Add(assemblyPath);
        }
        else
        {
            startInfo.FileName = processPath;
        }

        startInfo.ArgumentList.Add("--child");
        startInfo.ArgumentList.Add(engine);
        startInfo.ArgumentList.Add(pattern);
        startInfo.ArgumentList.Add(input);
        startInfo.ArgumentList.Add(testId.ToString(CultureInfo.InvariantCulture));

        return startInfo;
    }

    static void TryKillProcessTree(Process process)
    {
        try
        {
            process.Kill(entireProcessTree: true);
        }
        catch (Exception)
        {
        }
    }

    static Dictionary<string, SummaryStat> CalculateSummaryStats(
        List<SingleTestResult> allResults,
        List<RegexLibrary> libraries
    )
    {
        var summary = new Dictionary<string, SummaryStat>();

        foreach (var library in libraries)
        {
            var results = allResults.Where(r => r.Library == library.Name).ToList();
            var times = results
                .Where(r => !r.Result.TimedOut)
                .Select(r => r.Result.Time)
                .OrderBy(t => t)
                .ToList();

            var totalCount = results.Count;
            var timeoutCount = results.Count(r => r.Result.TimedOut);
            double? mean = null;
            double? median = null;
            if (times.Count > 0)
            {
                mean = times.Sum() / times.Count;
                median = times.Count % 2 == 0
                    ? (times[times.Count / 2 - 1] + times[times.Count / 2]) / 2
                    : times[times.Count / 2];
            }

            summary[library.Name] = new SummaryStat
            {
                MeanTime = mean,
                MedianTime = median,
                MinTime = times.Count > 0 ? times.First() : null,
                MaxTime = times.Count > 0 ? times.Last() : null,
                TimeoutCount = timeoutCount,
                TotalCount = totalCount
            };
        }

        return summary;
    }

    static void SaveResults(
        List<SingleTestResult> allResults,
        Dictionary<string, SummaryStat> summaryStats,
        List<RegexLibrary> libraries,
        int numRuns,
        int testsCount,
        double timeoutSeconds
    )
    {
        var testCasesPath = FindFilePath("test_cases.json");
        if (string.IsNullOrWhiteSpace(testCasesPath))
        {
            throw new FileNotFoundException("Unable to locate test_cases.json.");
        }

        var timeoutText = TimeoutLabel(timeoutSeconds);
        var outputPath = Path.Combine(
            Path.GetDirectoryName(testCasesPath) ?? ".",
            $"csharp_redos_test_results_timeout-{timeoutText}.json"
        );
        var outputData = new ResultsFile
        {
            Metadata = new Metadata
            {
                Timestamp = DateTimeOffset.UtcNow.ToString("o", CultureInfo.InvariantCulture),
                TotalRuns = numRuns,
                TotalTests = testsCount,
                TotalLibraries = libraries.Count,
                Libraries = libraries.Select(lib => lib.Name).ToList()
            },
            SummaryStats = summaryStats,
            Results = allResults
        };

        var options = new JsonSerializerOptions
        {
            WriteIndented = true
        };

        File.WriteAllText(outputPath, JsonSerializer.Serialize(outputData, options));
        Console.WriteLine($"Saved {allResults.Count} results to {outputPath}");
    }

    static string? FindFilePath(string fileName)
    {
        var candidates = new List<string?>
        {
            Directory.GetCurrentDirectory(),
            AppContext.BaseDirectory
        };

        foreach (var start in candidates)
        {
            if (string.IsNullOrWhiteSpace(start))
            {
                continue;
            }

            var dir = new DirectoryInfo(start);
            while (dir != null)
            {
                var candidate = Path.Combine(dir.FullName, fileName);
                if (File.Exists(candidate))
                {
                    return candidate;
                }

                dir = dir.Parent;
            }
        }

        return null;
    }

    static int ParseIntArg(string[] args, string flag, int defaultValue)
    {
        var raw = GetArgValue(args, flag);
        if (raw == null)
        {
            return defaultValue;
        }

        if (!int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value))
        {
            throw new ArgumentException($"Invalid value for {flag}: {raw}");
        }

        return value;
    }

    static double ParseDoubleArg(string[] args, string flag, double defaultValue)
    {
        var raw = GetArgValue(args, flag);
        if (raw == null)
        {
            return defaultValue;
        }

        if (!double.TryParse(raw, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out var value))
        {
            throw new ArgumentException($"Invalid value for {flag}: {raw}");
        }

        return value;
    }

    static int? ParseNullableIntArg(string[] args, string flag)
    {
        var raw = GetArgValue(args, flag);
        if (raw == null)
        {
            return null;
        }

        if (!int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value))
        {
            throw new ArgumentException($"Invalid value for {flag}: {raw}");
        }

        return value;
    }

    static string? GetArgValue(string[] args, string flag)
    {
        var prefix = $"{flag}=";
        foreach (var arg in args)
        {
            if (arg.StartsWith(prefix, StringComparison.Ordinal))
            {
                return arg[prefix.Length..];
            }
        }

        return null;
    }

    static bool HasFlag(string[] args, string flag)
    {
        return args.Any(arg => string.Equals(arg, flag, StringComparison.Ordinal));
    }

    static string TimeoutLabel(double timeoutSeconds)
    {
        if (Math.Abs(timeoutSeconds - Math.Round(timeoutSeconds)) < 1e-9)
        {
            return ((int)Math.Round(timeoutSeconds)).ToString(CultureInfo.InvariantCulture);
        }

        return timeoutSeconds.ToString("0.###", CultureInfo.InvariantCulture).Replace(".", "_");
    }

    static string RepeatString(string value, int count)
    {
        if (count <= 0)
        {
            return string.Empty;
        }

        return string.Concat(Enumerable.Repeat(value, count));
    }
}

class RegexLibrary
{
    public string Name { get; set; } = "";
    public string Engine { get; set; } = "";
    public TimeSpan Timeout { get; set; }
}

class TestCase
{
    [JsonPropertyName("id")]
    public int Id { get; set; }

    [JsonPropertyName("regex")]
    public string Regex { get; set; } = "";

    [JsonPropertyName("repeat")]
    public string Repeat { get; set; } = "";

    [JsonPropertyName("description")]
    public string Description { get; set; } = "";
}

class TestCaseRun
{
    public int Id { get; set; }
    public string Pattern { get; set; } = "";
    public string Input { get; set; } = "";
}

class ChildResult
{
    [JsonPropertyName("match")]
    public bool? Match { get; set; }

    [JsonPropertyName("error")]
    public string? Error { get; set; }
}

class LibraryResult
{
    [JsonPropertyName("library")]
    public string Library { get; set; } = "";

    [JsonPropertyName("result")]
    public bool? Result { get; set; }

    [JsonPropertyName("time")]
    public double Time { get; set; }

    [JsonPropertyName("timed_out")]
    public bool TimedOut { get; set; }
}

class SingleTestResult
{
    [JsonPropertyName("test_id")]
    public int TestId { get; set; }

    [JsonPropertyName("pattern")]
    public string Pattern { get; set; } = "";

    [JsonPropertyName("input")]
    public string Input { get; set; } = "";

    [JsonPropertyName("library")]
    public string Library { get; set; } = "";

    [JsonPropertyName("result")]
    public LibraryResult Result { get; set; } = new LibraryResult();
}

class SummaryStat
{
    [JsonPropertyName("mean_time")]
    public double? MeanTime { get; set; }

    [JsonPropertyName("median_time")]
    public double? MedianTime { get; set; }

    [JsonPropertyName("min_time")]
    public double? MinTime { get; set; }

    [JsonPropertyName("max_time")]
    public double? MaxTime { get; set; }

    [JsonPropertyName("timeout_count")]
    public int TimeoutCount { get; set; }

    [JsonPropertyName("total_count")]
    public int TotalCount { get; set; }
}

class Metadata
{
    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = "";

    [JsonPropertyName("total_runs")]
    public int TotalRuns { get; set; }

    [JsonPropertyName("total_tests")]
    public int TotalTests { get; set; }

    [JsonPropertyName("total_libraries")]
    public int TotalLibraries { get; set; }

    [JsonPropertyName("libraries")]
    public List<string> Libraries { get; set; } = new List<string>();
}

class ResultsFile
{
    [JsonPropertyName("metadata")]
    public Metadata Metadata { get; set; } = new Metadata();

    [JsonPropertyName("summary_stats")]
    public Dictionary<string, SummaryStat> SummaryStats { get; set; } = new Dictionary<string, SummaryStat>();

    [JsonPropertyName("results")]
    public List<SingleTestResult> Results { get; set; } = new List<SingleTestResult>();
}
