import { Worker } from "worker_threads";
import { readFileSync, writeFileSync } from "fs";
import { performance } from "perf_hooks";
import RE2 from "re2";

type TestCase = {
  id: number;
  regex: string;
  repeat: string;
  description: string;
};

type LibraryResult = {
  library: string;
  result: boolean | null;
  time: number;
  timed_out: boolean;
};

type SingleTestResult = {
  test_id: number;
  pattern: string;
  input: string;
  library: string;
  result: LibraryResult;
};

type ScalingTestEntry = {
  test_id: number;
  size: number;
  result: SingleTestResult[];
};

type RegexLibrary = {
  name: string;
  engine: "native" | "re2";
  timeoutMs: number;
};

const DEFAULT_TIMEOUT_MS = 2000;
const RESULTS_PATH = new URL("../ts_redos_test_results.json", import.meta.url);
const SCALING_RESULTS_PATH = new URL("../ts_scaling_test.json", import.meta.url);

function loadTestCases(): TestCase[] {
  const testCasesPath = new URL("../test_cases.json", import.meta.url);
  const raw = readFileSync(testCasesPath, "utf-8");
  return JSON.parse(raw) as TestCase[];
}

function getTestCases(inputSize = 20): Array<{ pattern: string; input: string }> {
  const cases = loadTestCases();
  return cases.map((entry) => ({
    pattern: entry.regex,
    input: entry.repeat.repeat(inputSize),
  }));
}

function runRegexWithTimeout(
  pattern: string,
  text: string,
  timeoutMs: number,
  engine: "native" | "re2",
): Promise<boolean> {
  return new Promise((resolve, reject) => {
    const workerSource =
      engine === "re2"
        ? `
      const { parentPort } = require('worker_threads');
      try {
        const RE2 = require('re2');
        const regex = new RE2(${JSON.stringify(pattern)});
        const match = regex.test(${JSON.stringify(text)});
        parentPort.postMessage({ success: true, match });
      } catch (err) {
        parentPort.postMessage({ success: false, error: err.message || String(err) });
      }
    `
        : `
      const { parentPort } = require('worker_threads');
      try {
        const regex = new RegExp(${JSON.stringify(pattern)});
        const match = regex.test(${JSON.stringify(text)});
        parentPort.postMessage({ success: true, match });
      } catch (err) {
        parentPort.postMessage({ success: false, error: err.message || String(err) });
      }
    `;

    const worker = new Worker(workerSource, { eval: true });

    const timer = setTimeout(() => {
      worker.terminate();
      reject(new Error("Regex timed out"));
    }, timeoutMs);

    worker.on("message", (msg) => {
      clearTimeout(timer);
      if (msg.success) {
        resolve(msg.match);
      } else {
        reject(new Error(msg.error));
      }
    });

    worker.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

function getLibraries(): RegexLibrary[] {
  return [
    { name: "NativeRegExp", engine: "native", timeoutMs: DEFAULT_TIMEOUT_MS },
    { name: "RE2", engine: "re2", timeoutMs: DEFAULT_TIMEOUT_MS },
  ];
}

async function runSingleTest(
  testId: number,
  libraries: RegexLibrary[],
  inputSize = 20,
): Promise<SingleTestResult[]> {
  const tests = getTestCases(inputSize);

  if (testId < 1 || testId > tests.length) {
    throw new Error(`Invalid test_id. Must be between 1 and ${tests.length}`);
  }

  const { pattern, input } = tests[testId - 1];
  const results: SingleTestResult[] = [];

  for (const library of libraries) {
    const start = performance.now();
    try {
      const match = await runRegexWithTimeout(
        pattern,
        input,
        library.timeoutMs,
        library.engine,
      );
      const duration = (performance.now() - start) / 1000;
      results.push({
        test_id: testId,
        pattern,
        input,
        library: library.name,
        result: {
          library: library.name,
          result: match,
          time: duration,
          timed_out: false,
        },
      });
    } catch (err) {
      const duration = (performance.now() - start) / 1000;
      const timedOut = err instanceof Error && err.message === "Regex timed out";
      results.push({
        test_id: testId,
        pattern,
        input,
        library: library.name,
        result: {
          library: library.name,
          result: null,
          time: duration,
          timed_out: timedOut,
        },
      });
    }
  }

  return results;
}

async function runAllTests(
  numRuns: number,
  libraries: RegexLibrary[],
  inputSize: number,
): Promise<SingleTestResult[]> {
  const tests = getTestCases(inputSize);
  const allResults: SingleTestResult[] = [];

  for (let run = 0; run < numRuns; run += 1) {
    console.log(`Run ${run + 1}/${numRuns}`);
    for (let testIdx = 0; testIdx < tests.length; testIdx += 1) {
      const { pattern, input } = tests[testIdx];
      for (const library of libraries) {
        const start = performance.now();
        try {
          const match = await runRegexWithTimeout(
            pattern,
            input,
            library.timeoutMs,
            library.engine,
          );
          const duration = (performance.now() - start) / 1000;
          allResults.push({
            test_id: testIdx + 1,
            pattern,
            input,
            library: library.name,
            result: {
              library: library.name,
              result: match,
              time: duration,
              timed_out: false,
            },
          });
        } catch (err) {
          const duration = (performance.now() - start) / 1000;
          const timedOut = err instanceof Error && err.message === "Regex timed out";
          allResults.push({
            test_id: testIdx + 1,
            pattern,
            input,
            library: library.name,
            result: {
              library: library.name,
              result: null,
              time: duration,
              timed_out: timedOut,
            },
          });
        }
      }
    }
  }

  return allResults;
}

function calculateSummaryStats(
  allResults: SingleTestResult[],
  libraries: RegexLibrary[],
): Record<
  string,
  {
    mean_time: number | null;
    median_time: number | null;
    min_time: number | null;
    max_time: number | null;
    timeout_count: number;
    total_count: number;
  }
> {
  const summary: Record<string, any> = {};

  for (const library of libraries) {
    const results = allResults.filter((r) => r.library === library.name);
    const times = results
      .filter((r) => !r.result.timed_out)
      .map((r) => r.result.time)
      .sort((a, b) => a - b);

    const totalCount = results.length;
    const timeoutCount = results.filter((r) => r.result.timed_out).length;
    const mean =
      times.length > 0
        ? times.reduce((sum, time) => sum + time, 0) / times.length
        : null;
    const median =
      times.length > 0
        ? times.length % 2 === 0
          ? (times[times.length / 2 - 1] + times[times.length / 2]) / 2
          : times[Math.floor(times.length / 2)]
        : null;

    summary[library.name] = {
      mean_time: mean,
      median_time: median,
      min_time: times.length > 0 ? times[0] : null,
      max_time: times.length > 0 ? times[times.length - 1] : null,
      timeout_count: timeoutCount,
      total_count: totalCount,
    };
  }

  return summary;
}

function saveResults(
  allResults: SingleTestResult[],
  summaryStats: ReturnType<typeof calculateSummaryStats>,
  libraries: RegexLibrary[],
  numRuns: number,
  testsCount: number,
): void {
  const outputData = {
    metadata: {
      timestamp: new Date().toISOString(),
      total_runs: numRuns,
      total_tests: testsCount,
      total_libraries: libraries.length,
      libraries: libraries.map((lib) => lib.name),
    },
    summary_stats: summaryStats,
    results: allResults,
  };

  writeFileSync(RESULTS_PATH, JSON.stringify(outputData, null, 2));
  console.log(`Saved ${allResults.length} results to ${RESULTS_PATH.pathname}`);
}

async function runScalingTest(
  libraries: RegexLibrary[],
  maxSize = 30,
): Promise<void> {
  const tests = getTestCases(0);
  const allResults: ScalingTestEntry[] = [];

  for (let testId = 1; testId <= tests.length; testId += 1) {
    for (let size = 0; size < maxSize; size += 1) {
      const results = await runSingleTest(testId, libraries, size);
      allResults.push({ test_id: testId, size, result: results });
    }
  }

  writeFileSync(SCALING_RESULTS_PATH, JSON.stringify(allResults, null, 2));
  console.log(`Saved scaling results to ${SCALING_RESULTS_PATH.pathname}`);
}

function getArgValue(flag: string): string | null {
  const prefix = `${flag}=`;
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith(prefix)) {
      return arg.slice(prefix.length);
    }
  }
  return null;
}

async function main(): Promise<void> {
  const libraries = getLibraries();
  const inputSize = Number(getArgValue("--input-size") ?? "20");
  const numRuns = Number(getArgValue("--runs") ?? "3");
  const singleTestId = getArgValue("--single");

  if (process.argv.includes("--scaling")) {
    await runScalingTest(libraries, Number(getArgValue("--max-size") ?? "30"));
    return;
  }

  if (singleTestId !== null) {
    const results = await runSingleTest(
      Number(singleTestId),
      libraries,
      inputSize,
    );
    for (const result of results) {
      console.log(`${result.library}: ${result.result.result}`);
    }
    return;
  }

  const allResults = await runAllTests(numRuns, libraries, inputSize);
  const summaryStats = calculateSummaryStats(allResults, libraries);
  saveResults(allResults, summaryStats, libraries, numRuns, getTestCases(0).length);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
