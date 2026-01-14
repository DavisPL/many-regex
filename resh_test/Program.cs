using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using Resharp;
using DotnetRegex = System.Text.RegularExpressions.Regex;

class Program
{
    static void Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--child")
        {
            RunChild(args);
            return;
        }

        const int inputSize = 100;
        var perTestTimeout = TimeSpan.FromSeconds(5);
        var tests = GetTestCases(inputSize);

        var totalStopwatch = Stopwatch.StartNew();
        var testId = 1;

        foreach (var (pattern, input) in tests)
        {
            RunTestWithTimeout("RE#", pattern, input, testId, perTestTimeout);
            RunTestWithTimeout("dotnet", pattern, input, testId, perTestTimeout);
            testId++;
        }

        totalStopwatch.Stop();
        Console.WriteLine($"Total time: {totalStopwatch.Elapsed.TotalMilliseconds:F3} ms");
    }

    static void RunChild(string[] args)
    {
        if (args.Length < 5)
        {
            Console.Error.WriteLine("Child invocation requires engine, pattern, input, and testId.");
            return;
        }

        var engine = args[1];
        var pattern = args[2];
        var input = args[3];
        var testId = int.Parse(args[4], CultureInfo.InvariantCulture);

        if (engine == "RE#")
        {
            RunTest("RE#", () => new Regex(pattern).IsMatch(input), pattern, input, testId);
            return;
        }

        if (engine == "dotnet")
        {
            RunTest("dotnet", () => new DotnetRegex(pattern).IsMatch(input), pattern, input, testId);
            return;
        }

        Console.Error.WriteLine($"Unknown engine: {engine}");
    }

    static void RunTestWithTimeout(
        string engine,
        string pattern,
        string input,
        int testId,
        TimeSpan timeout
    )
    {
        var startInfo = CreateChildProcessStartInfo(engine, pattern, input, testId);
        using var process = Process.Start(startInfo);

        if (process == null)
        {
            Console.WriteLine(
                $"Test {testId} ({engine}): pattern={pattern}, input_length={input.Length}, error=ProcessStartFailed, message=Failed to start child process"
            );
            return;
        }

        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();

        if (!process.WaitForExit((int)timeout.TotalMilliseconds))
        {
            TryKillProcessTree(process);
            Console.WriteLine(
                $"Test {testId} ({engine}): pattern={pattern}, input_length={input.Length}, error=TimeoutException, message=Exceeded {timeout.TotalSeconds:F0} seconds"
            );
            return;
        }

        var stdout = stdoutTask.Result;
        var stderr = stderrTask.Result;

        if (!string.IsNullOrWhiteSpace(stdout))
        {
            Console.Write(stdout);
        }

        if (!string.IsNullOrWhiteSpace(stderr))
        {
            Console.Write(stderr);
        }
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
            // Ignore kill failures; timeout is already reported.
        }
    }

    static void RunTest(
        string engine,
        Func<bool> isMatch,
        string pattern,
        string input,
        int testId
    )
    {
        try
        {
            var stopwatch = Stopwatch.StartNew();
            var match = isMatch();
            stopwatch.Stop();

            Console.WriteLine(
                $"Test {testId} ({engine}): pattern={pattern}, input_length={input.Length}, match={match}, time_ms={stopwatch.Elapsed.TotalMilliseconds:F3}"
            );
        }
        catch (Exception ex)
        {
            Console.WriteLine(
                $"Test {testId} ({engine}): pattern={pattern}, input_length={input.Length}, error={ex.GetType().Name}, message={ex.Message}"
            );
        }
    }

    static List<(string Pattern, string Input)> GetTestCases(int inputSize = 20)
    {
        return new List<(string, string)>
        {
            // Classic nested quantifiers
            ("^(a+)+$", RepeatChar('a', inputSize) + "B"),
            ("^(a*)*$", RepeatChar('a', inputSize) + "B"),
            ("^(a+)+b$", RepeatChar('a', inputSize) + "c"),
            // Alternation with overlapping patterns
            ("^(a|a)*$", RepeatChar('a', inputSize) + "B"),
            ("^(a|ab)*$", RepeatChar('a', inputSize) + "B"),
            ("(a|a|a|a|a|b)*c", RepeatChar('a', inputSize + 5) + "d"),
            // Nested groups with quantifiers
            ("^((a+)+)+$", RepeatChar('a', inputSize - 2) + "B"),
            ("^(a*)*b$", RepeatChar('a', inputSize) + "c"),
            ("^(a+)*b$", RepeatChar('a', inputSize) + "c"),
            // Email-like patterns (common real-world ReDoS)
            (
                @"^([a-zA-Z0-9])(([\-.]|[_]+)?([a-zA-Z0-9]+))*(@){1}[a-z0-9]+[.]{1}(([a-z]{2,3})|([a-z]{2,3}[.]{1}[a-z]{2,3}))$",
                RepeatChar('a', inputSize + 10) + "@"
            ),
            // Overlapping character classes
            ("^([a-z]+)+[A-Z]$", RepeatChar('a', inputSize + 5) + "1"),
            ("^([0-9a-z]+)+[A-Z]$", RepeatChar('a', inputSize + 5) + "!"),
            // Grouping with wildcards
            ("^(.*)*$", RepeatChar('a', inputSize) + "B"),
            ("^(.+)+$", RepeatChar('a', inputSize) + "B"),
            ("^(.*)+b$", RepeatChar('a', inputSize) + "c"),
            // Multiple overlapping quantifiers
            ("^(a*)+b$", RepeatChar('a', inputSize + 5) + "c"),
            ("^(a?)+b$", RepeatChar('a', inputSize + 5) + "c"),
            ("^(a*?)*b$", RepeatChar('a', inputSize) + "c"),
            // Word boundary catastrophic cases
            (@"^(\w+\s*)+$", RepeatString("a ", inputSize - 5) + "!"),
            (@"^([\w]+[\s]*)*$", RepeatString("test ", inputSize / 2) + "!"),
            // Digit patterns
            (@"^(\d+)+$", RepeatChar('1', inputSize + 5) + "a"),
            ("^([0-9]+)*$", RepeatChar('9', inputSize + 5) + "x"),
            // Complex alternation
            ("^(a+|a+)+$", RepeatChar('a', inputSize) + "B"),
            ("^(a*|a*)*$", RepeatChar('a', inputSize) + "B"),
            ("^(aa+|a+)+$", RepeatChar('a', inputSize + 2) + "B"),
            // Real-world URL pattern (simplified)
            (@"^(http://)?([a-z]+\.)*[a-z]+\.[a-z]{2,}$", RepeatString("http://a.", inputSize / 2) + "!"),
            // Whitespace patterns
            (@"^(\s*a+\s*)+$", RepeatString(" a", inputSize - 5) + "!"),
            (@"^(\s+|a+)*b$", RepeatString("a ", inputSize - 5) + "c"),
            // Optional group patterns
            ("^(a+)?b?(a+)?$", RepeatChar('a', inputSize + 5) + "c"),
            ("^(a+b?)+c$", RepeatChar('a', inputSize) + "d"),
            // Character class repetition
            ("^([a-zA-Z]+)*$", RepeatChar('a', inputSize + 5) + "1"),
            ("^([a-z0-9]+)+[!]$", RepeatString("abc123", inputSize / 4) + "?"),
            // Nested alternation
            ("^((a|b)+)+c$", RepeatChar('a', inputSize + 5) + "d"),
            ("^((a|ab)+)+c$", RepeatChar('a', inputSize) + "d"),
            // Long repeating patterns
            ("^(a+b)+c$", RepeatString("ab", inputSize - 5) + "d"),
            ("^(ab+)+c$", RepeatString("ab", inputSize - 5) + "d"),
            // Overlapping alternation and ambiguous prefixes
            ("^(a|aa)+$", RepeatChar('a', inputSize) + "B"),
            ("^(a|aa)*b$", RepeatChar('a', inputSize) + "c"),
            ("^(ab|a)+$", RepeatString("ab", inputSize / 2) + "aB"),
            ("^(ab|a)*b$", RepeatString("ab", inputSize / 2) + "a"),
            // Nested character class repetition
            ("^([ab]*)*c$", RepeatChar('a', inputSize) + "d"),
            ("^([ab]+)+c$", RepeatChar('a', inputSize) + "d"),
            ("^(a|b|ab)+c$", RepeatString("ab", inputSize / 2) + "d"),
            ("^([a-z]*[A-Z]?)*$", RepeatChar('a', inputSize) + "!"),
            // Repetition of repeated groups
            ("^((ab)*)*$", RepeatString("ab", inputSize / 2) + "c"),
            ("^((ab)+)*$", RepeatString("ab", inputSize / 2) + "c"),
            // Dot-heavy ambiguity
            ("^(a.*a)*$", "a" + RepeatChar('a', inputSize) + "B"),
            ("^(.*a)*$", RepeatChar('a', inputSize) + "B"),
            ("^(.+a)+$", RepeatChar('a', inputSize) + "B"),
            ("^(.*ab)*$", RepeatString("ab", inputSize / 2) + "c"),
            ("^((a|ab)*)*$", RepeatChar('a', inputSize) + "B"),
            // Alternation with longer branches
            ("^(a|ab|aba)+b$", RepeatChar('a', inputSize) + "c"),
            // Digit/word class interactions
            ("^([0-9]*[a-z]?)+$", RepeatChar('1', inputSize) + "!"),
            (@"^(\d*\d)+$", RepeatChar('1', inputSize) + "a"),
            (@"^((\d+)?)+$", RepeatChar('1', inputSize) + "a"),
            (@"^(\d+\s*)+$", RepeatString("1 ", inputSize - 5) + "!"),
            (@"^(\w+\W*)+$", RepeatString("a!", inputSize - 5) + "_"),
            (@"^(\w*\W+)*$", RepeatString("a!", inputSize / 2) + "a"),
            // Mixed alpha-numeric repeats
            (@"^([a-z]+\d+)*$", RepeatString("a1", inputSize / 2) + "B"),
            (@"^([a-z]+\d+)+$", RepeatString("a1", inputSize / 2) + "B"),
            (@"^([a-z]?\d?)+$", RepeatString("a1", inputSize / 2) + "B"),
            // Bounded repeats
            ("^(a{0,3})+b$", RepeatChar('a', inputSize) + "c"),
            ("^(a{1,3})+b$", RepeatChar('a', inputSize) + "c"),
            ("^([a-z]{1,3})+$", RepeatChar('a', inputSize) + "!"),
            ("^([a-z]{0,3})*b$", RepeatChar('a', inputSize) + "c"),
            // Optional-heavy nesting
            ("^((a?)+)+$", RepeatChar('a', inputSize) + "B"),
            ("^(a?b?)+c$", RepeatChar('a', inputSize) + "d"),
            ("^(a*b*)+c$", RepeatChar('a', inputSize) + "d"),
            ("^([ab]?)+c$", RepeatChar('a', inputSize) + "d"),
            ("^(a+|aa+)+$", RepeatChar('a', inputSize) + "B"),
            ("^((a|aa)+)+$", RepeatChar('a', inputSize) + "B"),
            (@"^([\s\S]+)+$", RepeatChar('a', inputSize) + "B"),
            // Backreferences and nested groups
            ("^(a|aa)+\\1$", RepeatChar('a', inputSize) + "B"),
            ("^((a|aa)+)\\1$", RepeatChar('a', inputSize) + "B"),
            ("^([ab]+)\\1c$", RepeatChar('a', inputSize) + "d"),
            ("^(a+)(a+)+\\1$", RepeatChar('a', inputSize) + "B"),
            ("^((a+)b)+\\2$", RepeatString("ab", inputSize / 2) + "B"),
            // Lookarounds with repeats
            ("^(?=(a+)+b)\\w+$", RepeatChar('a', inputSize) + "c"),
            ("^(?:(?!b).)*b$", RepeatChar('a', inputSize) + "c"),
            ("^(?=.*a.*a).*b$", RepeatChar('a', inputSize) + "c"),
            ("^((?=a).)+b$", RepeatChar('a', inputSize) + "c"),
            // Lazy/greedy interactions
            ("^(a+?)+$", RepeatChar('a', inputSize) + "B"),
            ("^(a+?)*b$", RepeatChar('a', inputSize) + "c"),
            ("^(a*?)+b$", RepeatChar('a', inputSize) + "c"),
            ("^(a+?b?)+c$", RepeatChar('a', inputSize) + "d"),
            // Anchors and alternation
            ("^((a|ab)*)+$", RepeatChar('a', inputSize) + "B"),
            ("^(a|a?)+b$", RepeatChar('a', inputSize) + "c"),
            ("^(a|a+)+b$", RepeatChar('a', inputSize) + "c"),
            ("^((a|ab)+)+$", RepeatChar('a', inputSize) + "B"),
            // Nested optional groups
            ("^((ab)?)+c$", RepeatString("ab", inputSize / 2) + "d"),
            ("^((a)?b?)+c$", RepeatChar('a', inputSize) + "d"),
            ("^((a?b?)+)+c$", RepeatChar('a', inputSize) + "d"),
            ("^((a?)+)+b$", RepeatChar('a', inputSize) + "c"),
            // Alternation with shared suffixes
            ("^(ab|cab)+d$", RepeatString("ab", inputSize / 2) + "c"),
            ("^(abcd|abc)+e$", RepeatString("abc", inputSize / 2) + "d"),
            ("^(abc|ab)+c$", RepeatString("ab", inputSize / 2) + "B"),
            // Character class overlaps
            ("^([a-f]+|[a-z]+)+$", RepeatChar('a', inputSize) + "B"),
            ("^([a-z0-9]+|[a-z]+)+$", RepeatChar('a', inputSize) + "!"),
            ("^([0-9a-f]+|[0-9]+)+$", RepeatChar('1', inputSize) + "g"),
            // Unicode-ish class behavior with ASCII inputs
            (@"^(\w+)+\W$", RepeatChar('a', inputSize) + "_"),
            (@"^(\D+)+\d$", RepeatChar('a', inputSize) + "b"),
            (@"^(\S+)+\s$", RepeatChar('a', inputSize) + "b"),
            // Repeats with fixed tokens
            ("^(ab?)+b$", RepeatChar('a', inputSize) + "c"),
            ("^(a?b)+b$", RepeatChar('a', inputSize) + "c"),
            ("^((ab)?b)+$", RepeatChar('a', inputSize) + "B"),
            ("^((ab)*)+b$", RepeatString("ab", inputSize / 2) + "c"),
            // More dot/star ambiguity
            ("^(.+)+b$", RepeatChar('a', inputSize) + "c"),
            ("^(.*a.*)+b$", RepeatChar('a', inputSize) + "c"),
            ("^(.*?a)+b$", RepeatChar('a', inputSize) + "c"),
            ("^((.*)a)+b$", RepeatChar('a', inputSize) + "c"),
            // Nested alternation with digits
            (@"^((\d+|\d{1,2})+)+$", RepeatChar('1', inputSize) + "a"),
            (@"^(\d{0,3})+\D$", RepeatChar('1', inputSize) + "a"),
            (@"^(\d{1,3})+\D$", RepeatChar('1', inputSize) + "a"),
        };
    }

    static string RepeatChar(char value, int count)
    {
        if (count <= 0)
        {
            return string.Empty;
        }

        return new string(value, count);
    }

    static string RepeatString(string value, int count)
    {
        if (count <= 0)
        {
            return string.Empty;
        }

        var builder = new StringBuilder(value.Length * count);
        for (var i = 0; i < count; i++)
        {
            builder.Append(value);
        }

        return builder.ToString();
    }
}
