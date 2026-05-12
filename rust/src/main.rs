use regex::Regex;

fn main() {
    let pat = Regex::new(r"[a-f]{4}").expect("Compile success");

    assert!(pat.is_match("aaaa"));
    assert!(pat.is_match("bcde"));

    assert!(!pat.is_match("aaa"));
    assert!(!pat.is_match("jjjj"));
}
