//! Convert strings and the keys of JSON objects between snake_case, camelCase, PascalCase and
//! kebab-case. A port of [pyhumps](https://github.com/nficano/humps) 3.8.0 that keeps its exact output,
//! quirks included.
//!
//! Every converter comes in two forms: `camelize(&str) -> String` for one string, and
//! `camelize_value(&Value) -> Value` for JSON. The `*_value` form rewrites object keys at every depth and
//! leaves all other values alone, so strings inside arrays and object values are never converted.
//!
//! ```
//! use serde_json::json;
//!
//! assert_eq!(humps::camelize("jack_in_the_box"), "jackInTheBox");
//! assert_eq!(humps::decamelize("APIResponse"), "api_response");
//! assert_eq!(humps::kebabize("white_castle"), "white-castle");
//! assert_eq!(
//!     humps::camelize_value(&json!({"fallback_url": ["dash_url"]})),
//!     json!({"fallbackUrl": ["dash_url"]}),
//! );
//! ```
//!
//! Like the original:
//!
//! - All whitespace (Python's `\s`) is removed, unless a converter returns its input unchanged. Every
//!   converter except `kebabize` and `dekebabize` does that for an all-uppercase string
//!   (`camelize("HELLO WORLD") == "HELLO WORLD"`), and all of them do it for a numeric one (`"123"`, `"三"`).
//! - At the top level, `*_value` treats `null` as `""`, booleans as `"True"`/`"False"` and numbers as their
//!   Python text, so `camelize_value(&json!(true)) == json!("true")`. When the converter returns its input
//!   unchanged, the original value comes back: `camelize_value(&json!(5)) == json!(5)`.
//! - Output objects keep the input's key order. When two keys convert to the same key, the first position
//!   and the last value win.
//! - `is_camelcase(x)` is `x == camelize(x)`, and so on for the other predicates, which makes `"API"` all
//!   four cases at once.

mod pyfmt;
mod unicode_tables;

use pyfmt::{py_float_repr, py_isnumeric, py_isupper, py_lower, py_lower_char, py_upper_char};
use regex::{Captures, Regex};
use serde_json::{Number, Value};
use std::borrow::Cow;
use std::sync::LazyLock;

// The two lookarounds of the original patterns are applied by hand where these are used.
static ACRONYM_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[A-Z\d]+").unwrap());
static PASCAL_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^\-_]+").unwrap());
static SPLIT_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[\-_]*[A-Z][^A-Z]*[\-_]*").unwrap());
static UNDERSCORE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[\-_]+[^\-_]").unwrap());
// Python's `\s` is White_Space plus U+001C..U+001F.
static WHITESPACE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[\s\x1C-\x1F]+").unwrap());

/// What a converter does with one string: hand back its input, or produce a new string.
enum Outcome {
    Original,
    Converted(String),
}

impl Outcome {
    fn into_string(self, original: &str) -> String {
        match self {
            Outcome::Original => original.to_owned(),
            Outcome::Converted(s) => s,
        }
    }
}

type Convert = fn(&str) -> Outcome;

fn strip_whitespace(s: &str) -> Cow<'_, str> {
    WHITESPACE_RE.replace_all(s, "")
}

fn is_separator(c: char) -> bool {
    c == '-' || c == '_'
}

fn upper_first(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars();
    if let Some(c) = chars.next() {
        py_upper_char(c, &mut out);
    }
    out.extend(chars);
    out
}

fn lower_first(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars();
    if let Some(c) = chars.next() {
        py_lower_char(c, &mut out);
    }
    out.extend(chars);
    out
}

fn first_two_chars(s: &str) -> &str {
    s.char_indices().nth(2).map_or(s, |(i, _)| &s[..i])
}

/// `UNDERSCORE_RE.sub(repl, s)` for `(?<=[^\-_])[\-_]+[^\-_]`; `repl` gets the match's last character.
fn sub_separators(s: &str, mut repl: impl FnMut(char, &mut String)) -> String {
    let mut out = String::with_capacity(s.len());
    let mut last = 0;
    for m in UNDERSCORE_RE.find_iter(s) {
        // The lookbehind reads the character before the match without consuming it, so a match may
        // follow the previous one directly ("a_b_c" -> "aBC").
        let follows_word = s[..m.start()]
            .chars()
            .next_back()
            .is_some_and(|c| !is_separator(c));
        let Some(next) = m.as_str().chars().next_back() else {
            continue;
        };
        if !follows_word {
            continue;
        }
        out.push_str(&s[last..m.start()]);
        repl(next, &mut out);
        last = m.end();
    }
    out.push_str(&s[last..]);
    out
}

/// `ACRONYM_RE.sub(lambda m: m.group(0).title(), s)` for `([A-Z\d]+)(?=[A-Z\d]|$)`.
fn fix_abbreviations(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut last = 0;
    for m in ACRONYM_RE.find_iter(s) {
        // The lookahead leaves the last character of a run that does not end the string to the next word.
        let end = match m.as_str().char_indices().next_back() {
            Some((i, _)) if m.end() != s.len() => m.start() + i,
            _ => m.end(),
        };
        if end == m.start() {
            continue;
        }
        out.push_str(&s[last..m.start()]);
        // `str.title` on ASCII capitals and decimal digits: a letter after a letter is lowercased.
        let mut after_letter = false;
        for c in s[m.start()..end].chars() {
            out.push(if after_letter {
                c.to_ascii_lowercase()
            } else {
                c
            });
            after_letter = c.is_ascii_alphabetic();
        }
        last = end;
    }
    out.push_str(&s[last..]);
    out
}

/// `separator.join(w for w in SPLIT_RE.split(s) if w)`, where the split keeps the matches.
fn separate_words(s: &str, separator: &str) -> String {
    let mut words = Vec::new();
    let mut last = 0;
    for m in SPLIT_RE.find_iter(s) {
        words.push(&s[last..m.start()]);
        words.push(m.as_str());
        last = m.end();
    }
    words.push(&s[last..]);
    words.retain(|w| !w.is_empty());
    words.join(separator)
}

fn camelize_outcome(raw: &str) -> Outcome {
    let s = strip_whitespace(raw);
    if py_isupper(&s) || py_isnumeric(&s) {
        return Outcome::Original;
    }
    let s = if !s.is_empty() && !py_isupper(first_two_chars(&s)) {
        Cow::Owned(lower_first(&s))
    } else {
        s
    };
    Outcome::Converted(sub_separators(&s, py_upper_char))
}

fn pascalize_outcome(raw: &str) -> Outcome {
    let s = strip_whitespace(raw);
    if py_isupper(&s) || py_isnumeric(&s) {
        return Outcome::Original;
    }
    let s = PASCAL_RE.replace_all(&s, |caps: &Captures| upper_first(&caps[0]));
    Outcome::Converted(upper_first(&camelize(&s)))
}

fn kebabize_outcome(raw: &str) -> Outcome {
    let s = strip_whitespace(raw);
    if py_isnumeric(&s) {
        return Outcome::Original;
    }
    if !py_isupper(&s) && (is_camelcase(&s) || is_pascalcase(&s)) {
        return Outcome::Converted(py_lower(&separate_words(&fix_abbreviations(&s), "-")));
    }
    Outcome::Converted(sub_separators(&s, |c, out| {
        out.push('-');
        out.push(c);
    }))
}

fn decamelize_outcome(raw: &str) -> Outcome {
    let s = strip_whitespace(raw);
    if py_isupper(&s) || py_isnumeric(&s) {
        return Outcome::Original;
    }
    Outcome::Converted(py_lower(&separate_words(&fix_abbreviations(&s), "_")))
}

fn dekebabize_outcome(raw: &str) -> Outcome {
    let s = strip_whitespace(raw);
    if py_isnumeric(&s) {
        return Outcome::Original;
    }
    Outcome::Converted(s.replace('-', "_"))
}

/// Python's `str()` of a JSON number: integers in decimal, floats as `repr`.
fn python_str(n: &Number) -> String {
    match n.as_f64() {
        Some(f) if n.is_f64() => py_float_repr(f),
        _ => n.to_string(),
    }
}

/// The top level of a `*_value` call: containers are walked, anything else takes the string path.
fn convert_value(value: &Value, convert: Convert) -> Value {
    let text = match value {
        Value::Array(_) | Value::Object(_) => return walk(value, convert),
        Value::String(s) => return Value::String(convert(s).into_string(s)),
        Value::Null => String::new(),
        Value::Bool(b) => if *b { "True" } else { "False" }.to_owned(),
        Value::Number(n) => python_str(n),
    };
    match convert(&text) {
        Outcome::Original => value.clone(),
        Outcome::Converted(s) => Value::String(s),
    }
}

// DIVERGENCE(oracle-depth-cap): output keeps every level; the Python oracle driver serializes at most 64
// levels, so fixtures deeper than that record a truncation marker instead of Python's real result.
// DIVERGENCE(recursion-depth): no depth limit. Python raises RecursionError near 990 levels; here the
// caller's stack bounds the depth (serde_json's parser already stops at 128).
fn walk(value: &Value, convert: Convert) -> Value {
    match value {
        Value::Array(items) => Value::Array(items.iter().map(|v| walk(v, convert)).collect()),
        // Collecting inserts in order: a repeated key keeps its first position and takes the last value.
        Value::Object(map) => Value::Object(
            map.iter()
                .map(|(k, v)| (convert(k).into_string(k), walk(v, convert)))
                .collect(),
        ),
        other => other.clone(),
    }
}

/// Converts a string to camelCase: `"fallback_url"` becomes `"fallbackUrl"`.
///
/// Leading and trailing separators stay, inner runs of `-` and `_` collapse
/// (`"__scrubber_media___url_"` becomes `"__scrubberMediaUrl_"`). An all-uppercase or numeric string comes
/// back unchanged.
pub fn camelize(s: &str) -> String {
    camelize_outcome(s).into_string(s)
}

/// Converts a string to PascalCase: `"red_robin"` becomes `"RedRobin"`.
///
/// Each word is capitalized and the result goes through [`camelize`], which leaves an all-uppercase
/// result alone: `"a_b"` becomes `"A_B"`.
pub fn pascalize(s: &str) -> String {
    pascalize_outcome(s).into_string(s)
}

/// Converts a string to kebab-case: `"white_castle"` becomes `"white-castle"`.
///
/// A camelCase or PascalCase string is split and lowercased (`"APIResponse"` becomes `"api-response"`);
/// anything else has its separator runs replaced with `-`, keeping case
/// (`"scrubber_Media_Url"` becomes `"scrubber-Media-Url"`).
pub fn kebabize(s: &str) -> String {
    kebabize_outcome(s).into_string(s)
}

/// Converts a string to snake_case: `"rubyTuesdays"` becomes `"ruby_tuesdays"`.
///
/// Acronyms count as one word (`"APIResponse"` becomes `"api_response"`).
pub fn decamelize(s: &str) -> String {
    decamelize_outcome(s).into_string(s)
}

/// Converts a PascalCase string to snake_case. The same as [`decamelize`].
pub fn depascalize(s: &str) -> String {
    decamelize(s)
}

/// Converts a kebab-case string to snake_case by replacing every `-` with `_`, keeping case.
pub fn dekebabize(s: &str) -> String {
    dekebabize_outcome(s).into_string(s)
}

/// Whether `s == camelize(s)`.
pub fn is_camelcase(s: &str) -> bool {
    s == camelize(s)
}

/// Whether `s == pascalize(s)`.
pub fn is_pascalcase(s: &str) -> bool {
    s == pascalize(s)
}

/// Whether `s == kebabize(s)`.
pub fn is_kebabcase(s: &str) -> bool {
    s == kebabize(s)
}

/// Whether `s == decamelize(s)`, except that kebab-case strings that are not camelCase are not snake_case.
pub fn is_snakecase(s: &str) -> bool {
    if is_kebabcase(s) && !is_camelcase(s) {
        return false;
    }
    s == decamelize(s)
}

/// [`camelize`] for JSON: converts object keys at every depth.
pub fn camelize_value(value: &Value) -> Value {
    convert_value(value, camelize_outcome)
}

/// [`pascalize`] for JSON: converts object keys at every depth.
pub fn pascalize_value(value: &Value) -> Value {
    convert_value(value, pascalize_outcome)
}

/// [`kebabize`] for JSON: converts object keys at every depth.
pub fn kebabize_value(value: &Value) -> Value {
    convert_value(value, kebabize_outcome)
}

/// [`decamelize`] for JSON: converts object keys at every depth.
pub fn decamelize_value(value: &Value) -> Value {
    convert_value(value, decamelize_outcome)
}

/// [`depascalize`] for JSON. The same as [`decamelize_value`].
pub fn depascalize_value(value: &Value) -> Value {
    decamelize_value(value)
}

/// [`dekebabize`] for JSON: converts object keys at every depth.
pub fn dekebabize_value(value: &Value) -> Value {
    convert_value(value, dekebabize_outcome)
}

/// Whether `*value == camelize_value(value)`.
pub fn is_camelcase_value(value: &Value) -> bool {
    *value == camelize_value(value)
}

/// Whether `*value == pascalize_value(value)`.
pub fn is_pascalcase_value(value: &Value) -> bool {
    *value == pascalize_value(value)
}

/// Whether `*value == kebabize_value(value)`.
pub fn is_kebabcase_value(value: &Value) -> bool {
    *value == kebabize_value(value)
}

/// [`is_snakecase`] for JSON.
pub fn is_snakecase_value(value: &Value) -> bool {
    if is_kebabcase_value(value) && !is_camelcase_value(value) {
        return false;
    }
    *value == decamelize_value(value)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn keys(value: &Value) -> Vec<&str> {
        value
            .as_object()
            .expect("an object")
            .keys()
            .map(String::as_str)
            .collect()
    }

    /// [ref: tests/test_separate_words.py::test_separate_words]
    #[test]
    fn separate_words_rows() {
        let rows = [
            ("HelloWorld", "Hello_World"),
            ("_HelloWorld", "_Hello_World"),
            ("__HelloWorld", "__Hello_World"),
            ("HelloWorld_", "Hello_World_"),
            ("HelloWorld__", "Hello_World__"),
            ("helloWorld", "hello_World"),
            ("_helloWorld", "_hello_World"),
            ("__helloWorld", "__hello_World"),
            ("helloWorld_", "hello_World_"),
            ("helloWorld__", "hello_World__"),
            ("hello_world", "hello_world"),
            ("_hello_world", "_hello_world"),
            ("__hello_world", "__hello_world"),
            ("hello_world_", "hello_world_"),
            ("hello_world__", "hello_world__"),
            ("whatever_hi", "whatever_hi"),
            ("whatever_10", "whatever_10"),
            ("sizeX", "size_X"),
            ("aB", "a_B"),
            ("testNTest", "test_N_Test"),
        ];
        for (input, expected) in rows {
            assert_eq!(separate_words(input, "_"), expected, "{input:?}");
        }
    }

    #[test]
    fn separate_words_keeps_separators_next_to_capitals() {
        assert_eq!(separate_words("__a_B", "-"), "__a-_B");
        assert_eq!(separate_words("a-B", "-"), "a--B");
        assert_eq!(separate_words("_A", "-"), "_A");
    }

    #[test]
    fn lookbehind_does_not_consume() {
        let rows = [
            ("a_b_c", "aBC"),
            ("a-b_c", "aBC"),
            ("_a", "_a"),
            ("_a_b", "_aB"),
            ("-_a", "-_a"),
            ("a__b", "aB"),
            ("a_", "a_"),
            ("a_é", "aÉ"),
            ("a_ß", "aSS"),
        ];
        for (input, expected) in rows {
            assert_eq!(camelize(input), expected, "camelize({input:?})");
        }
        assert_eq!(kebabize("a_b_c"), "a-b-c");
        assert_eq!(kebabize("_a_b"), "_a-b");
        assert_eq!(kebabize("a__b-c"), "a-b-c");
    }

    #[test]
    fn lookahead_leaves_the_next_capital() {
        let rows = [
            ("ABc", "ABc"),
            ("APIResponse", "ApiResponse"),
            ("MB2X", "Mb2X"),
            ("A\u{661}", "A\u{661}"),
            ("B52Thing", "B52Thing"),
            ("BIP72b", "Bip72b"),
            ("aBC", "aBc"),
            ("A1B2", "A1B2"),
        ];
        for (input, expected) in rows {
            assert_eq!(fix_abbreviations(input), expected, "{input:?}");
        }
    }

    #[test]
    fn objects_keep_key_order() {
        let input = json!({"b_x": 1, "a_y": 2, "c_z": 3});
        let before = input.clone();
        let out = camelize_value(&input);
        assert_eq!(keys(&out), ["bX", "aY", "cZ"]);
        assert_eq!(input, before);
        assert_eq!(keys(&input), ["b_x", "a_y", "c_z"]);

        let nested = camelize_value(&json!([{"z_a": {"y_b": 0, "x_c": 0}}]));
        assert_eq!(keys(&nested[0]), ["zA"]);
        assert_eq!(keys(&nested[0]["zA"]), ["yB", "xC"]);
    }

    #[test]
    fn key_collision_keeps_first_position_and_last_value() {
        let out = camelize_value(&json!({"a_b": 1, "x": 0, "aB": 2}));
        assert_eq!(keys(&out), ["aB", "x"]);
        assert_eq!(out["aB"], json!(2));

        let out = decamelize_value(&json!({"x": 0, "aB": 1, "y": 0, "a_b": 2}));
        assert_eq!(keys(&out), ["x", "a_b", "y"]);
        assert_eq!(out["a_b"], json!(2));
    }

    #[test]
    fn only_keys_convert() {
        assert_eq!(camelize_value(&json!(["a_b"])), json!(["a_b"]));
        assert_eq!(
            camelize_value(&json!({"a_b": ["c_d", {"e_f": "g_h"}]})),
            json!({"aB": ["c_d", {"eF": "g_h"}]})
        );
    }

    #[test]
    fn top_level_scalars_take_the_string_path() {
        assert_eq!(camelize_value(&Value::Null), json!(""));
        assert_eq!(camelize_value(&json!(true)), json!("true"));
        assert_eq!(dekebabize_value(&json!(false)), json!("False"));
        assert_eq!(camelize_value(&json!(5)), json!(5));
        assert_eq!(camelize_value(&json!(-5)), json!("-5"));
        assert_eq!(dekebabize_value(&json!(-5)), json!("_5"));
        assert_eq!(camelize_value(&json!(1e-5)), json!("1e05"));
        assert_eq!(decamelize_value(&json!(1e16)), json!("1e+16"));
        assert!(is_camelcase_value(&json!(5)));
        assert!(!is_camelcase_value(&Value::Null));
    }

    #[test]
    fn early_return_keeps_whitespace() {
        assert_eq!(camelize("HELLO WORLD"), "HELLO WORLD");
        assert_eq!(kebabize("HELLO WORLD"), "HELLOWORLD");
        assert_eq!(kebabize("HELLO world"), "hell-oworld");
        assert_eq!(camelize("a\u{1c}_b"), "aB");
    }
}

#[cfg(test)]
mod unicode_version_tests {
    use super::*;

    #[test]
    fn unicode_tables_cover_this_toolchain() {
        // The tables in unicode_tables.rs are deltas against std's Unicode 17 data and regex-syntax's
        // Unicode 16 classes; a newer toolchain or regex-syntax needs them regenerated.
        assert!(char::UNICODE_VERSION <= (17, 0, 0));
        assert!(!Regex::new(r"\d").unwrap().is_match("\u{11de0}"));
    }

    #[test]
    fn case_mapping_follows_cpython_unicode_16() {
        assert_eq!(kebabize("\u{a7ce}"), "\u{a7ce}");
        assert_eq!(camelize("a_\u{a7cf}"), "a\u{a7cf}");
        assert!(is_snakecase("a\u{a7ce}"));
        assert_eq!(decamelize("ab\u{a7d3}C"), "ab\u{a7d3}_c");
        assert_eq!(decamelize("aΣ"), "aς");
    }
}
