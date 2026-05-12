use regex::Regex;
use std::time::Duration;

fn ast_depth(pattern: &Regex) -> usize {
    todo!("Measure the regex AST depth of {}", pattern)
}

fn num_loops(pattern: &Regex) -> usize {
    todo!("Measure the number of loops of {}", pattern)
}

fn compile_time(pattern: String) -> Duration {
    todo!("Measure the compile time of {}", pattern)
}

fn test_regex(pattern: String, input: String) {
    let pat = Regex::new(&pattern).expect("Should compile");

    // TODO: Measure these
    // 1. memory usage
    // 2. regex match time

    // 3. regex compile time (input independent)
    let comp_time: Duration = compile_time(pattern);
    // 4. AST depth (input independent)
    let ast_dep: usize = ast_depth(&pat);
    // 5. number of loops (input independent)
    let num_loops: usize = num_loops(&pat);
}

fn main() {
    let pat = Regex::new(r"[a-f]{4}").expect("Compile success");

    assert!(pat.is_match("aaaa"));
    assert!(pat.is_match("bcde"));

    assert!(!pat.is_match("aaa"));
    assert!(!pat.is_match("jjjj"));
}
