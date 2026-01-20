import { Worker } from "worker_threads";
import { readFileSync } from "fs";
import RE2 from "re2";
import { Regolith } from "@regolithjs/regolith";

type TestCase = {
  regex: string;
  repeat: string;
};

type RegexLibrary = {
  name: string;
  engine: "native" | "re2" | "regolith";
  timeoutMs: number;
};

const RUNS = 3;
const INPUT_SIZE = 20;
const DEFAULT_TIMEOUT_MS = 2000;

function loadTestCases(): TestCase[] {
  const raw = readFileSync(new URL("../test_cases.json", import.meta.url), "utf-8");
  return JSON.parse(raw) as TestCase[];
}

function getTestCases(inputSize = 20): Array<{ pattern: string; input: string }> {
  const cases = loadTestCases();
  return cases.map((entry) => ({
    pattern: entry.regex,
    input: entry.repeat.repeat(inputSize),
  }));
}

function getLibraries(): RegexLibrary[] {
  return [
    { name: "NativeRegExp", engine: "native", timeoutMs: DEFAULT_TIMEOUT_MS },
    { name: "RE2", engine: "re2", timeoutMs: DEFAULT_TIMEOUT_MS },
    { name: "Regolith", engine: "regolith", timeoutMs: DEFAULT_TIMEOUT_MS },
  ];
}

function runRegexWithTimeout(
  pattern: string,
  text: string,
  timeoutMs: number,
  engine: "native" | "re2" | "regolith",
): Promise<void> {
  return new Promise((resolve) => {
    const workerSource =
      engine === "re2"
        ? `
      const { parentPort } = require('worker_threads');
      try {
        const RE2 = require('re2');
        const regex = new RE2(${JSON.stringify(pattern)});
        regex.test(${JSON.stringify(text)});
        parentPort.postMessage({ ok: true });
      } catch (err) {
        parentPort.postMessage({ ok: false, error: err.message || String(err) });
      }
    `
        : engine === "regolith"
        ? `
      const { parentPort } = require('worker_threads');
      try {
        const { Regolith } = require('@regolithjs/regolith');
        const regex = new Regolith(${JSON.stringify(pattern)});
        regex.test(${JSON.stringify(text)});
        parentPort.postMessage({ ok: true });
      } catch (err) {
        parentPort.postMessage({ ok: false, error: err.message || String(err) });
      }
    `
        : `
      const { parentPort } = require('worker_threads');
      try {
        const regex = new RegExp(${JSON.stringify(pattern)});
        regex.test(${JSON.stringify(text)});
        parentPort.postMessage({ ok: true });
      } catch (err) {
        parentPort.postMessage({ ok: false, error: err.message || String(err) });
      }
    `;

    let settled = false;
    const worker = new Worker(workerSource, { eval: true });
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      worker.terminate().finally(resolve);
    }, timeoutMs);

    worker.on("message", () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      worker.terminate().finally(resolve);
    });
    worker.on("error", () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve();
    });
    worker.on("exit", () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve();
    });
  });
}

async function main(): Promise<void> {
  const libraries = getLibraries();
  const tests = getTestCases(INPUT_SIZE);

  for (let run = 0; run < RUNS; run += 1) {
    console.log(`Run ${run + 1}/${RUNS}`);
    for (let testIdx = 0; testIdx < tests.length; testIdx += 1) {
      const { pattern, input } = tests[testIdx];
      for (const library of libraries) {
        console.log(`Engine=${library.engine} Pattern=${pattern}`);
        try {
          await runRegexWithTimeout(
            pattern,
            input,
            library.timeoutMs,
            library.engine,
          );
        } catch {
          // Intentionally ignore per-test failures.
        }
      }
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
