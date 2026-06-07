import { Worker } from "worker_threads";
import { readFileSync, writeFileSync, readdirSync } from "fs";
import { resolve as resolvePath, join as joinPath } from "path";
import { performance } from "perf_hooks";
import { createRequire } from "module";
// RE2 and Regolith are loaded via createRequire() on demand. They are not
// imported at the top level so this file loads under node even when one of
// them isn't installed (only the engines actually exercised need to resolve).
const req = createRequire(import.meta.url);

type TestCase = {
  id: number;
  regex: string;
  repeat: string;
  description: string;
};

/** New-schema per-case JSON written by misc-scripts/build_dataset.py. */
type DatasetCase = {
  id: number;
  regex: string;
  input: string;
  regex_size?: number;
  input_size?: number;
  ast_size?: number;
  ast_depth?: number;
  group?: string;
  size?: string;
};

/** Per-case metadata carried into every result entry when running the new
 *  dataset; undefined for the legacy test_cases.json flow. */
type CaseMetadata = {
  group?: string;
  size?: string;
  ast_size?: number;
  ast_depth?: number;
  regex_size?: number;
  input_size?: number;
};

type PreparedCase = {
  test_id: number;
  pattern: string;
  input: string;
  metadata?: CaseMetadata;
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
  metadata?: CaseMetadata;
};

type ScalingTestEntry = {
  test_id: number;
  size: number;
  result: SingleTestResult[];
};

type RegexLibrary = {
  name: string;
  engine: "native" | "re2" | "regolith";
  timeoutMs: number;
};

const DEFAULT_TIMEOUT_SECONDS = 2;
const DEFAULT_TIMEOUT_MS = DEFAULT_TIMEOUT_SECONDS * 1000;
const SCALING_RESULTS_PATH = new URL("../ts_scaling_test.json", import.meta.url);

function loadTestCases(): TestCase[] {
  const testCasesPath = new URL("../test_cases.json", import.meta.url);
  const raw = readFileSync(testCasesPath, "utf-8");
  return JSON.parse(raw) as TestCase[];
}

function getTestCases(inputSize = 50): PreparedCase[] {
  const cases = loadTestCases();
  return cases.map((entry, i) => ({
    test_id: entry.id ?? i + 1,
    pattern: entry.regex,
    input: entry.repeat.repeat(inputSize),
  }));
}

/** Load every *.json file under [datasetDir] as a new-schema DatasetCase. */
function getDatasetCases(datasetDir: string): PreparedCase[] {
  const absDir = resolvePath(datasetDir);
  const files = readdirSync(absDir)
    .filter((f) => f.endsWith(".json"))
    .sort();

  return files.map((f) => {
    const raw = readFileSync(joinPath(absDir, f), "utf-8");
    const c = JSON.parse(raw) as DatasetCase;
    return {
      test_id: c.id,
      pattern: c.regex,
      input: c.input,
      metadata: {
        group: c.group,
        size: c.size,
        ast_size: c.ast_size,
        ast_depth: c.ast_depth,
        regex_size: c.regex_size,
        input_size: c.input_size,
      },
    };
  });
}

/** Synchronous in-process match. No timeout: a pathological native RegExp
 *  can hang the whole run. Use --in-process only with engines you trust
 *  (RE2 has linear-time guarantees; native and Regolith do not). */
function runRegexInProcess(
  pattern: string,
  text: string,
  engine: "native" | "re2" | "regolith",
): boolean {
  if (engine === "re2") {
    const RE2: any = req("re2");
    return new RE2(pattern).test(text);
  }
  if (engine === "regolith") {
    const { Regolith }: any = req("@regolithjs/regolith");
    return new Regolith(pattern).test(text);
  }
  return new RegExp(pattern).test(text);
}

function runRegexWithTimeout(
  pattern: string,
  text: string,
  timeoutMs: number,
  engine: "native" | "re2" | "regolith",
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
        : engine === "regolith"
        ? `
      const { parentPort } = require('worker_threads');
      try {
        const { Regolith } = require('@regolithjs/regolith');
        const regex = new Regolith(${JSON.stringify(pattern)});
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

function getLibraries(timeoutMs: number): RegexLibrary[] {
  return [
    { name: "NativeRegExp", engine: "native", timeoutMs },
    { name: "RE2", engine: "re2", timeoutMs },
    { name: "Regolith", engine: "regolith", timeoutMs },
  ];
}

async function runSingleTest(
  testId: number,
  libraries: RegexLibrary[],
  tests: PreparedCase[],
  inProcess: boolean = false,
): Promise<SingleTestResult[]> {
  if (testId < 1 || testId > tests.length) {
    throw new Error(`Invalid test_id. Must be between 1 and ${tests.length}`);
  }

  const c = tests[testId - 1];
  const { pattern, input, metadata } = c;
  const results: SingleTestResult[] = [];

  for (const library of libraries) {
    const start = performance.now();
    try {
      const match = inProcess
        ? runRegexInProcess(pattern, input, library.engine)
        : await runRegexWithTimeout(
            pattern,
            input,
            library.timeoutMs,
            library.engine,
          );
      const duration = (performance.now() - start) / 1000;
      results.push({
        test_id: c.test_id,
        pattern,
        input,
        library: library.name,
        result: {
          library: library.name,
          result: match,
          time: duration,
          timed_out: false,
        },
        ...(metadata ? { metadata } : {}),
      });
    } catch (err) {
      const duration = (performance.now() - start) / 1000;
      const timedOut = err instanceof Error && err.message === "Regex timed out";
      results.push({
        test_id: c.test_id,
        pattern,
        input,
        library: library.name,
        result: {
          library: library.name,
          result: null,
          time: duration,
          timed_out: timedOut,
        },
        ...(metadata ? { metadata } : {}),
      });
    }
  }

  return results;
}

async function runAllTests(
  numRuns: number,
  libraries: RegexLibrary[],
  tests: PreparedCase[],
  inProcess: boolean = false,
): Promise<SingleTestResult[]> {
  const allResults: SingleTestResult[] = [];

  for (let run = 0; run < numRuns; run += 1) {
    console.log(`Run ${run + 1}/${numRuns}${inProcess ? " (in-process)" : ""}`);
    for (let testIdx = 0; testIdx < tests.length; testIdx += 1) {
      const c = tests[testIdx];
      const { pattern, input, metadata } = c;
      for (const library of libraries) {
        const start = performance.now();
        try {
          const match = inProcess
            ? runRegexInProcess(pattern, input, library.engine)
            : await runRegexWithTimeout(
                pattern,
                input,
                library.timeoutMs,
                library.engine,
              );
          const duration = (performance.now() - start) / 1000;
          allResults.push({
            test_id: c.test_id,
            pattern,
            input,
            library: library.name,
            result: {
              library: library.name,
              result: match,
              time: duration,
              timed_out: false,
            },
            ...(metadata ? { metadata } : {}),
          });
        } catch (err) {
          const duration = (performance.now() - start) / 1000;
          const timedOut = err instanceof Error && err.message === "Regex timed out";
          allResults.push({
            test_id: c.test_id,
            pattern,
            input,
            library: library.name,
            result: {
              library: library.name,
              result: null,
              time: duration,
              timed_out: timedOut,
            },
            ...(metadata ? { metadata } : {}),
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

    // Match python/main.py semantics: counts are per execution (runs * tests).
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
  outputPath: URL,
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

  writeFileSync(outputPath, JSON.stringify(outputData, null, 2));
  console.log(`Saved ${allResults.length} results to ${outputPath.pathname}`);
}

async function runScalingTest(
  libraries: RegexLibrary[],
  maxSize = 30,
): Promise<void> {
  const allResults: ScalingTestEntry[] = [];
  // Scaling test only operates on the legacy schema (varies input length).
  for (let size = 0; size < maxSize; size += 1) {
    const tests = getTestCases(size);
    for (let testId = 1; testId <= tests.length; testId += 1) {
      const results = await runSingleTest(testId, libraries, tests);
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

function timeoutLabel(timeoutSeconds: number): string {
  if (Number.isInteger(timeoutSeconds)) {
    return `${timeoutSeconds}`;
  }
  return `${timeoutSeconds}`.replace(".", "_");
}

function buildOutputPath(timeoutSeconds: number, dataset: boolean,
                          inProcess: boolean): URL {
  const tag = (dataset ? "_dataset" : "") + (inProcess ? "_inproc" : "");
  return new URL(
    `../ts_redos_test_results${tag}_timeout-${timeoutLabel(timeoutSeconds)}.json`,
    import.meta.url,
  );
}

async function main(): Promise<void> {
  const timeoutSeconds = Number(
    getArgValue("--timeout") ?? `${DEFAULT_TIMEOUT_SECONDS}`,
  );
  const timeoutMs = timeoutSeconds * 1000;
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error(`Invalid value for --timeout: ${timeoutSeconds}`);
  }

  const libraries = getLibraries(timeoutMs);
  const inputSize = Number(
    getArgValue("--input-length") ?? getArgValue("--input-size") ?? "50",
  );
  const numRuns = Number(getArgValue("--runs") ?? "3");
  const singleTestId = getArgValue("--single");
  const datasetDir = getArgValue("--dataset");
  const inProcess = process.argv.includes("--in-process");
  const tests = datasetDir !== null
    ? getDatasetCases(datasetDir)
    : getTestCases(inputSize);
  const outputPath = buildOutputPath(timeoutSeconds, datasetDir !== null, inProcess);

  if (process.argv.includes("--scaling")) {
    await runScalingTest(libraries, Number(getArgValue("--max-size") ?? "50"));
    return;
  }

  if (singleTestId !== null) {
    const results = await runSingleTest(
      Number(singleTestId),
      libraries,
      tests,
      inProcess,
    );
    for (const result of results) {
      console.log(`${result.library}: ${result.result.result}`);
    }
    return;
  }

  const allResults = await runAllTests(numRuns, libraries, tests, inProcess);
  const summaryStats = calculateSummaryStats(allResults, libraries);
  saveResults(
    allResults,
    summaryStats,
    libraries,
    numRuns,
    tests.length,
    outputPath,
  );
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
