use chrono::Local;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::Path;
use std::time::Instant;

#[derive(Deserialize)]
struct TestCase {
    regex: String,
    repeat: String,
}

/// New-schema per-case JSON produced by `misc-scripts/build_dataset.py`.
#[derive(Deserialize)]
struct DatasetCase {
    id: usize,
    regex: String,
    input: String,
    #[serde(default)]
    regex_size: Option<usize>,
    #[serde(default)]
    input_size: Option<usize>,
    #[serde(default)]
    ast_size: Option<i64>,
    #[serde(default)]
    ast_depth: Option<i64>,
    #[serde(default)]
    group: Option<String>,
    #[serde(default)]
    size: Option<String>,
}

/// Materialized per-case run input. `metadata` is `Some` only for new-schema
/// dataset cases; `None` preserves the original `test_cases.json` flow.
#[derive(Clone)]
struct PreparedCase {
    test_id: usize,
    pattern: String,
    input: String,
    character: String,
    count: usize,
    metadata: Option<CaseMetadata>,
}

#[derive(Serialize, Clone)]
struct CaseMetadata {
    group: Option<String>,
    size: Option<String>,
    ast_size: Option<i64>,
    ast_depth: Option<i64>,
    regex_size: Option<usize>,
    input_size: Option<usize>,
}

#[derive(Serialize, Clone)]
struct LibraryResult {
    library: String,
    result: Option<bool>,
    time: f64,
    timed_out: bool,
}

#[derive(Serialize)]
struct ResultEntry {
    run: usize,
    test_id: usize,
    pattern: String,
    character: String,
    count: usize,
    library: String,
    result: LibraryResult,
    #[serde(skip_serializing_if = "Option::is_none")]
    metadata: Option<CaseMetadata>,
}

#[derive(Serialize)]
struct SummaryStats {
    mean_time: Option<f64>,
    median_time: Option<f64>,
    min_time: Option<f64>,
    max_time: Option<f64>,
    timeout_count: usize,
    timeout_tests_count: usize,
    successful_count: usize,
    total_count: usize,
    total_test_cases: usize,
    run_count: usize,
}

#[derive(Serialize)]
struct Metadata {
    timestamp: String,
    total_runs: usize,
    total_tests: usize,
    total_libraries: usize,
    libraries: Vec<String>,
}

#[derive(Serialize)]
struct Output {
    metadata: Metadata,
    summary_stats: BTreeMap<String, SummaryStats>,
    results: Vec<ResultEntry>,
}

const LIBRARY_NAME: &str = "Regex";

/// Input sizes (in characters) swept per dataset case when no explicit
/// `--input-sweep` is given. Large steps keep the run cheap while still
/// covering ~1k–200k so the input-size axis of the heatmaps is populated.
/// The dataset's "size" dimension varies the *regex*; this varies the *input*.
const DEFAULT_INPUT_SWEEP: &[usize] =
    &[1_000, 10_000, 25_000, 50_000, 75_000, 100_000, 150_000, 200_000];

/// Rebuild an input of exactly `target` characters from a dataset case's base
/// string by repeating then truncating it. The dataset inputs are runs of a
/// single repeat unit (e.g. "a" or "a "), so any prefix/extension is still a
/// valid same-character input. Inputs are ASCII, so byte and char lengths
/// coincide and truncation lands on a char boundary.
fn resize_input(base: &str, target: usize) -> String {
    if target == 0 || base.is_empty() {
        return String::new();
    }
    let mut s = String::with_capacity(target);
    while s.len() < target {
        s.push_str(base);
    }
    s.truncate(target);
    s
}

/// Expand each base dataset case into one [PreparedCase] per swept input size,
/// rebuilding the input to that length and overriding `input_size`/`count`.
fn expand_with_sweep(cases: Vec<PreparedCase>, sweep: &[usize]) -> Vec<PreparedCase> {
    let mut out = Vec::with_capacity(cases.len() * sweep.len());
    for case in cases {
        for &target in sweep {
            let input = resize_input(&case.input, target);
            let count = input.len();
            let mut metadata = case.metadata.clone();
            if let Some(md) = metadata.as_mut() {
                md.input_size = Some(count);
            }
            out.push(PreparedCase {
                test_id: case.test_id,
                pattern: case.pattern.clone(),
                input,
                character: case.character.clone(),
                count,
                metadata,
            });
        }
    }
    out
}

fn get_test_cases(input_size: usize) -> Vec<PreparedCase> {
    let data = fs::read_to_string("test_cases.json").expect("read test_cases.json");
    let cases: Vec<TestCase> = serde_json::from_str(&data).expect("parse test_cases.json");
    cases
        .into_iter()
        .enumerate()
        .map(|(i, c)| {
            let input = c.repeat.repeat(input_size);
            PreparedCase {
                test_id: i + 1,
                pattern: c.regex,
                input,
                character: c.repeat,
                count: input_size,
                metadata: None,
            }
        })
        .collect()
}

/// Load every `*.json` file in [dataset_dir] as a new-schema [DatasetCase] and
/// materialize it into a [PreparedCase]. Files are sorted by filename so the
/// run order is stable and matches `id`.
fn get_dataset_cases(dataset_dir: &Path) -> Vec<PreparedCase> {
    let mut files: Vec<_> = fs::read_dir(dataset_dir)
        .unwrap_or_else(|e| panic!("read dataset dir {:?}: {}", dataset_dir, e))
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().and_then(|s| s.to_str()) == Some("json"))
        .collect();
    files.sort();

    files
        .into_iter()
        .map(|path| {
            let data = fs::read_to_string(&path)
                .unwrap_or_else(|e| panic!("read {:?}: {}", path, e));
            let c: DatasetCase = serde_json::from_str(&data)
                .unwrap_or_else(|e| panic!("parse {:?}: {}", path, e));
            let count = c.input.len();
            PreparedCase {
                test_id: c.id,
                pattern: c.regex,
                input: c.input,
                character: String::new(),
                count,
                metadata: Some(CaseMetadata {
                    group: c.group,
                    size: c.size,
                    ast_size: c.ast_size,
                    ast_depth: c.ast_depth,
                    regex_size: c.regex_size,
                    input_size: c.input_size,
                }),
            }
        })
        .collect()
}

fn run_library_match(pattern: &str, input: &str) -> LibraryResult {
    let start = Instant::now();
    let result = match Regex::new(pattern) {
        Ok(re) => Some(re.is_match(input)),
        Err(_) => None,
    };
    let duration = start.elapsed().as_secs_f64();
    LibraryResult {
        library: LIBRARY_NAME.to_string(),
        result,
        time: if result.is_some() { duration } else { 0.0 },
        timed_out: false,
    }
}

fn run_all_tests(num_runs: usize, tests: &[PreparedCase]) -> Vec<ResultEntry> {
    let mut all_results: Vec<ResultEntry> = Vec::new();

    println!(
        "Running {} iterations of {} tests with {} library...",
        num_runs,
        tests.len(),
        LIBRARY_NAME
    );

    for run in 0..num_runs {
        println!("\nRun {}/{}", run + 1, num_runs);
        for case in tests.iter() {
            println!("  {} - Test {}", LIBRARY_NAME, case.test_id);
            let res = run_library_match(&case.pattern, &case.input);
            all_results.push(ResultEntry {
                run: run + 1,
                test_id: case.test_id,
                pattern: case.pattern.clone(),
                character: case.character.clone(),
                count: case.count,
                library: LIBRARY_NAME.to_string(),
                result: res,
                metadata: case.metadata.clone(),
            });
        }
    }

    all_results
}

fn calculate_summary_stats(all_results: &[ResultEntry]) -> BTreeMap<String, SummaryStats> {
    let mut summary = BTreeMap::new();

    let lib_results: Vec<&ResultEntry> = all_results
        .iter()
        .filter(|r| r.library == LIBRARY_NAME)
        .collect();

    let unique_test_ids: std::collections::HashSet<usize> =
        lib_results.iter().map(|r| r.test_id).collect();
    let run_ids: std::collections::HashSet<usize> = lib_results.iter().map(|r| r.run).collect();

    let mut times: Vec<f64> = Vec::new();
    let mut timeout_count = 0usize;
    let mut timeout_test_ids: std::collections::HashSet<usize> = std::collections::HashSet::new();

    for r in &lib_results {
        if r.result.timed_out {
            timeout_count += 1;
            timeout_test_ids.insert(r.test_id);
        } else if r.result.result.is_some() {
            times.push(r.result.time);
        }
    }

    let stats = if !times.is_empty() {
        let mut sorted = times.clone();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let n = sorted.len();
        let median = if n % 2 == 1 {
            sorted[n / 2]
        } else {
            (sorted[n / 2 - 1] + sorted[n / 2]) / 2.0
        };
        SummaryStats {
            mean_time: Some(times.iter().sum::<f64>() / n as f64),
            median_time: Some(median),
            min_time: Some(sorted[0]),
            max_time: Some(sorted[n - 1]),
            timeout_count,
            timeout_tests_count: timeout_test_ids.len(),
            successful_count: n,
            total_count: lib_results.len(),
            total_test_cases: unique_test_ids.len(),
            run_count: run_ids.len(),
        }
    } else {
        SummaryStats {
            mean_time: None,
            median_time: None,
            min_time: None,
            max_time: None,
            timeout_count,
            timeout_tests_count: timeout_test_ids.len(),
            successful_count: 0,
            total_count: lib_results.len(),
            total_test_cases: unique_test_ids.len(),
            run_count: run_ids.len(),
        }
    };

    summary.insert(LIBRARY_NAME.to_string(), stats);
    summary
}

fn print_summary_stats(summary: &BTreeMap<String, SummaryStats>) {
    println!("\nSummary Statistics:");
    for (lib_name, stats) in summary {
        println!("\n{}:", lib_name);
        if let Some(mean) = stats.mean_time {
            println!("  Mean time: {:.6}s", mean);
            println!("  Median time: {:.6}s", stats.median_time.unwrap());
            println!("  Min time: {:.6}s", stats.min_time.unwrap());
            println!("  Max time: {:.6}s", stats.max_time.unwrap());
        } else {
            println!("  No successful completions");
        }
        println!(
            "  Timeouts (executions): {}/{}",
            stats.timeout_count, stats.total_count
        );
        println!(
            "  Timeout test cases (unique): {}/{}",
            stats.timeout_tests_count, stats.total_test_cases
        );
        println!(
            "  Runs: {} | Unique test cases: {}",
            stats.run_count, stats.total_test_cases
        );
    }
}

fn save_results(
    all_results: Vec<ResultEntry>,
    summary_stats: BTreeMap<String, SummaryStats>,
    num_runs: usize,
    tests_count: usize,
    filename: &str,
) {
    let output = Output {
        metadata: Metadata {
            timestamp: Local::now().to_rfc3339(),
            total_runs: num_runs,
            total_tests: tests_count,
            total_libraries: 1,
            libraries: vec![LIBRARY_NAME.to_string()],
        },
        summary_stats,
        results: all_results,
    };

    let json = serde_json::to_string_pretty(&output).expect("serialize results");
    fs::write(filename, json).expect("write results file");
    println!(
        "\n{} total test results saved to {}",
        output.results.len(),
        filename
    );
}

struct Args {
    runs: usize,
    input_length: usize,
    dataset: Option<String>,
    /// In dataset mode, the input sizes (chars) to sweep per case. `None` means
    /// use [DEFAULT_INPUT_SWEEP]; an empty vec disables sweeping (use each
    /// case's stored input as-is).
    input_sweep: Option<Vec<usize>>,
}

fn parse_args() -> Args {
    let mut runs = 3usize;
    let mut input_length = 20usize;
    let mut dataset: Option<String> = None;
    let mut input_sweep: Option<Vec<usize>> = None;
    let mut iter = env::args().skip(1);
    while let Some(arg) = iter.next() {
        match arg.as_str() {
            "--runs" => {
                runs = iter
                    .next()
                    .and_then(|v| v.parse().ok())
                    .expect("--runs <usize>");
            }
            "--input-length" | "--input-size" => {
                input_length = iter
                    .next()
                    .and_then(|v| v.parse().ok())
                    .expect("--input-length <usize>");
            }
            "--dataset" => {
                dataset = Some(iter.next().expect("--dataset <path>"));
            }
            // Comma-separated input sizes to sweep, e.g.
            //   --input-sweep 10000,50000,100000
            // The literal `none` disables sweeping (stored input used as-is).
            "--input-sweep" => {
                let raw = iter.next().expect("--input-sweep <n,n,...|none>");
                input_sweep = Some(if raw.eq_ignore_ascii_case("none") {
                    Vec::new()
                } else {
                    raw.split(',')
                        .map(|s| s.trim().parse().expect("--input-sweep needs integers"))
                        .collect()
                });
            }
            other => panic!("unknown argument: {}", other),
        }
    }
    Args {
        runs,
        input_length,
        dataset,
        input_sweep,
    }
}

fn main() {
    let args = parse_args();
    let (tests, output_filename) = match args.dataset.as_ref() {
        Some(dir) => {
            let base = get_dataset_cases(Path::new(dir));
            // Sweep input size across each case. Default sweep unless the caller
            // overrode it; an explicit empty list keeps each stored input as-is.
            let sweep: &[usize] = match args.input_sweep.as_deref() {
                Some(s) => s,
                None => DEFAULT_INPUT_SWEEP,
            };
            let tests = if sweep.is_empty() {
                base
            } else {
                println!("Sweeping input sizes: {:?}", sweep);
                expand_with_sweep(base, sweep)
            };
            (tests, "rust_redos_test_results_dataset.json".to_string())
        }
        None => (
            get_test_cases(args.input_length),
            "rust_redos_test_results.json".to_string(),
        ),
    };
    let tests_count = tests.len();
    let all_results = run_all_tests(args.runs, &tests);
    let summary = calculate_summary_stats(&all_results);
    print_summary_stats(&summary);
    save_results(
        all_results,
        summary,
        args.runs,
        tests_count,
        &output_filename,
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn regex_test() {
        let pat = Regex::new(r"[a-f]{4}").expect("Compile success");

        assert!(pat.is_match("aaaa"));
        assert!(pat.is_match("bcde"));

        assert!(!pat.is_match("aaa"));
        assert!(!pat.is_match("jjjj"));
    }
}
