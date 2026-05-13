use regex::Regex;
use std::hint::black_box;
use std::time::{Duration, Instant};

fn ast_depth(pattern: &Regex) -> usize {
    todo!("Measure the regex AST depth of {}", pattern)
}

fn num_loops(pattern: String) -> usize {
    // This counts the loop operators
    // TODO: a more advances detection would find loops inside of loops and then multiply them
    // together

    let astrisks = pattern.matches("*").count();
    let plus = pattern.matches("+").count();

    // This adds two options only though
    let question = pattern.matches("?").count();

    let quantity = pattern.matches("{").count();

    return astrisks + plus + question + quantity;
}

fn compile_time(pattern: String) -> Duration {
    let start = Instant::now();
    // Prevent optimizing this compilation away
    black_box(Regex::new(&pattern).expect("Should compile"));
    return Instant::now() - start;
}

fn test_regex(pattern: String, input: String) {
    let pat = Regex::new(&pattern).expect("Should compile");

    // TODO: Measure these
    // 1. memory usage
    // 2. regex match time

    // 3. regex compile time (input independent)
    let comp_time: Duration = compile_time(pattern.clone());
    // 4. AST depth (input independent)
    let ast_dep: usize = ast_depth(&pat);
    // 5. number of loops (input independent)
    let num_loop: usize = num_loops(pattern);

    println!(
        "Compile time: {:?}, AST depth: {}, Num. loops: {}",
        comp_time, ast_dep, num_loop
    );
}

fn main() {
    test_regex("(a+)+".to_string(), "aaaaaaaaaaaaaaaaab".to_string());
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
