using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using Resharp;

class Program
{
    static void Main()
    {
        const int inputSize = 100;
        var tests = GetTestCases(inputSize);

        var totalStopwatch = Stopwatch.StartNew();
        var testId = 1;

        foreach (var (pattern, input) in tests)
        {
            var regex = new Regex(pattern);
            var stopwatch = Stopwatch.StartNew();
            var isMatch = regex.IsMatch(input);
            stopwatch.Stop();

            Console.WriteLine(
                $"Test {testId}: pattern={pattern}, input_length={input.Length}, match={isMatch}, time_ms={stopwatch.Elapsed.TotalMilliseconds:F3}"
            );
            testId++;
        }

        totalStopwatch.Stop();
        Console.WriteLine($"Total time: {totalStopwatch.Elapsed.TotalMilliseconds:F3} ms");
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
