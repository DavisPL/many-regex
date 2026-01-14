using System;
using Resharp;

class Program
{
    static void Main()
    {
        // Pattern
        var pattern = "hello.*world";

        // Inputs
        var inputs = new[]
        {
            "hello world",
            "hello brave new world",
            "world hello",
            "hello_world"
        };

        var regex = new Regex(pattern);

        foreach (var s in inputs)
        {
            if (regex.IsMatch(s))
            {
                Console.WriteLine($"MATCH: {s}");
            }
            else
            {
                Console.WriteLine($"NO MATCH: {s}");
            }
        }
    }
}
