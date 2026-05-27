use chrono::Local;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::time::Instant;

#[derive(Deserialize)]
struct TestCase {
    regex: String,
    repeat: String,
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

fn get_test_cases(input_size: usize) -> Vec<(String, String, usize)> {
    let data = fs::read_to_string("test_cases.json").expect("read test_cases.json");
    let cases: Vec<TestCase> = serde_json::from_str(&data).expect("parse test_cases.json");
    cases
        .into_iter()
        .map(|c| (c.regex, c.repeat, input_size))
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

fn run_all_tests(num_runs: usize, input_size: usize) -> Vec<ResultEntry> {
    let tests = get_test_cases(input_size);
    let mut all_results: Vec<ResultEntry> = Vec::new();

    println!(
        "Running {} iterations of {} tests with {} library...",
        num_runs,
        tests.len(),
        LIBRARY_NAME
    );
    println!("Input size multiplier: {}", input_size);

    for run in 0..num_runs {
        println!("\nRun {}/{}", run + 1, num_runs);
        for (test_idx, (pattern, character, count)) in tests.iter().enumerate() {
            println!("  {} - Test {}", LIBRARY_NAME, test_idx + 1);
            let input = character.repeat(*count);
            let res = run_library_match(pattern, &input);
            all_results.push(ResultEntry {
                run: run + 1,
                test_id: test_idx + 1,
                pattern: pattern.clone(),
                character: character.clone(),
                count: *count,
                library: LIBRARY_NAME.to_string(),
                result: res,
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
}

fn parse_args() -> Args {
    let mut runs = 3usize;
    let mut input_length = 20usize;
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
            other => panic!("unknown argument: {}", other),
        }
    }
    Args { runs, input_length }
}

fn main() {
    let args = parse_args();
    let all_results = run_all_tests(args.runs, args.input_length);
    let summary = calculate_summary_stats(&all_results);
    let tests_count = get_test_cases(args.input_length).len();
    print_summary_stats(&summary);
    save_results(
        all_results,
        summary,
        args.runs,
        tests_count,
        "rust_redos_test_results.json",
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
