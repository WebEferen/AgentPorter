//! Comparison core shared by every public function: the error type, the operator set, the semver
//! matcher, segment comparison and the JavaScript number semantics it depends on.

use std::cmp::Ordering;
use std::fmt;
use std::str::FromStr;

/// Every failure the crate reports.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Error {
    /// The input is not a version the semver grammar accepts. Holds the input unchanged.
    InvalidVersion(String),
    /// The operator is not one of `>`, `>=`, `=`, `<=`, `<`, `!=`.
    InvalidOperator,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::InvalidVersion(version) => {
                write!(
                    f,
                    "Invalid argument not valid semver ('{version}' received)"
                )
            }
            Error::InvalidOperator => {
                f.write_str("Invalid operator, expected one of >|>=|=|<=|<|!=")
            }
        }
    }
}

impl std::error::Error for Error {}

/// A comparison operator accepted by `compare`, parsed from `>`, `>=`, `=`, `<=`, `<` or `!=`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CompareOperator {
    /// `>`
    Greater,
    /// `>=`
    GreaterOrEqual,
    /// `=`
    Equal,
    /// `<=`
    LessOrEqual,
    /// `<`
    Less,
    /// `!=`
    NotEqual,
}

impl FromStr for CompareOperator {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self, Error> {
        match s {
            ">" => Ok(CompareOperator::Greater),
            ">=" => Ok(CompareOperator::GreaterOrEqual),
            "=" => Ok(CompareOperator::Equal),
            "<=" => Ok(CompareOperator::LessOrEqual),
            "<" => Ok(CompareOperator::Less),
            "!=" => Ok(CompareOperator::NotEqual),
            _ => Err(Error::InvalidOperator),
        }
    }
}

impl fmt::Display for CompareOperator {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            CompareOperator::Greater => ">",
            CompareOperator::GreaterOrEqual => ">=",
            CompareOperator::Equal => "=",
            CompareOperator::LessOrEqual => "<=",
            CompareOperator::Less => "<",
            CompareOperator::NotEqual => "!=",
        })
    }
}

/// The capture groups of the source's `semver` regex.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct SemverMatch<'a> {
    /// `[major, minor, patch, fourth]`. `major` is always present.
    pub(crate) segments: [Option<&'a str>; 4],
    pub(crate) prerelease: Option<&'a str>,
}

/// Matches the source regex
/// `/^[v^~<>=]*?(\d+)(?:\.([x*]|\d+)(?:\.([x*]|\d+)(?:\.([x*]|\d+))?(?:-([\da-z\-]+(?:\.[\da-z\-]+)*))?(?:\+[\da-z\-]+(?:\.[\da-z\-]+)*)?)?)?$/i`.
///
/// At every group boundary the next character decides the branch (the prefix set, digits, `.`, `-`
/// and `+` are disjoint), so backtracking can never produce another match and one forward scan
/// gives the same groups. `\d` and `/i` are ASCII only and `$` is the end of input, as in
/// ECMAScript without the `u` and `m` flags.
pub(crate) fn match_semver(version: &str) -> Option<SemverMatch<'_>> {
    let mut rest = version.trim_start_matches(['v', 'V', '^', '~', '<', '>', '=']);
    let mut m = SemverMatch {
        segments: [Some(take_digits(&mut rest)?), None, None, None],
        prerelease: None,
    };
    if rest.is_empty() {
        return Some(m);
    }
    rest = rest.strip_prefix('.')?;
    m.segments[1] = Some(take_segment(&mut rest)?);
    if rest.is_empty() {
        return Some(m);
    }
    rest = rest.strip_prefix('.')?;
    m.segments[2] = Some(take_segment(&mut rest)?);
    if let Some(tail) = rest.strip_prefix('.') {
        rest = tail;
        m.segments[3] = Some(take_segment(&mut rest)?);
    }
    if let Some(tail) = rest.strip_prefix('-') {
        rest = tail;
        m.prerelease = Some(take_identifiers(&mut rest)?);
    }
    if let Some(tail) = rest.strip_prefix('+') {
        rest = tail;
        take_identifiers(&mut rest)?;
    }
    rest.is_empty().then_some(m)
}

fn take_while_ascii<'a>(rest: &mut &'a str, pred: impl Fn(u8) -> bool) -> Option<&'a str> {
    let len = rest.bytes().take_while(|&b| pred(b)).count();
    if len == 0 {
        return None;
    }
    let (taken, tail) = rest.split_at(len);
    *rest = tail;
    Some(taken)
}

/// `\d+`
fn take_digits<'a>(rest: &mut &'a str) -> Option<&'a str> {
    take_while_ascii(rest, |b| b.is_ascii_digit())
}

/// `[x*]|\d+` under `/i`
fn take_segment<'a>(rest: &mut &'a str) -> Option<&'a str> {
    match rest.as_bytes().first()? {
        b'x' | b'X' | b'*' => {
            let (wildcard, tail) = rest.split_at(1);
            *rest = tail;
            Some(wildcard)
        }
        _ => take_digits(rest),
    }
}

/// `[\da-z\-]+(?:\.[\da-z\-]+)*` under `/i`
fn take_identifiers<'a>(rest: &mut &'a str) -> Option<&'a str> {
    let start = *rest;
    loop {
        take_while_ascii(rest, |b| b.is_ascii_alphanumeric() || b == b'-')?;
        match rest.strip_prefix('.') {
            Some(tail) => *rest = tail,
            None => break,
        }
    }
    Some(&start[..start.len() - rest.len()])
}

/// Source `validateAndParse`.
// DIVERGENCE(non-string-arguments): the source's `typeof` guard (`TypeError: Invalid argument expected
// string`) has no counterpart; `&str` makes non-string input unrepresentable.
pub(crate) fn validate_and_parse(version: &str) -> Result<SemverMatch<'_>, Error> {
    match_semver(version).ok_or_else(|| Error::InvalidVersion(version.to_owned()))
}

/// Source `compareSegments`: compares position by position up to the longer input and returns the
/// first difference. A missing or empty segment reads as `"0"` (`a[i] || '0'`).
pub(crate) fn compare_segments<'a, 'b>(
    a: impl IntoIterator<Item = Option<&'a str>>,
    b: impl IntoIterator<Item = Option<&'b str>>,
) -> Ordering {
    let (mut a, mut b) = (a.into_iter().fuse(), b.into_iter().fuse());
    loop {
        let (x, y) = match (a.next(), b.next()) {
            (None, None) => return Ordering::Equal,
            (x, y) => (or_zero(x.flatten()), or_zero(y.flatten())),
        };
        let r = compare_strings(x, y);
        if r.is_ne() {
            return r;
        }
    }
}

fn or_zero(segment: Option<&str>) -> &str {
    segment.filter(|s| !s.is_empty()).unwrap_or("0")
}

fn is_wildcard(s: &str) -> bool {
    matches!(s, "*" | "x" | "X")
}

enum Parsed<'a> {
    Number(f64),
    Text(&'a str),
}

fn try_parse(v: &str) -> Parsed<'_> {
    parse_int(v).map_or(Parsed::Text(v), Parsed::Number)
}

/// Source `compareStrings` with `forceType` folded in: a number against a string compares
/// `String(number)` with the string.
fn compare_strings(a: &str, b: &str) -> Ordering {
    if is_wildcard(a) || is_wildcard(b) {
        return Ordering::Equal;
    }
    match (try_parse(a), try_parse(b)) {
        // `parse_int` never yields NaN; JS `>` and `<` are both false for it anyway.
        (Parsed::Number(x), Parsed::Number(y)) => x.partial_cmp(&y).unwrap_or(Ordering::Equal),
        (Parsed::Text(x), Parsed::Text(y)) => x.cmp(y),
        (Parsed::Number(x), Parsed::Text(y)) => js_number_to_string(x).as_str().cmp(y),
        (Parsed::Text(x), Parsed::Number(y)) => x.cmp(js_number_to_string(y).as_str()),
    }
}

/// JavaScript `parseInt(s, 10)`: skips leading whitespace, takes an optional sign and the longest
/// ASCII digit prefix, rounded to the nearest `f64` (infinity past the `f64` range). `None` is the
/// source's `NaN` (no digits).
pub(crate) fn parse_int(s: &str) -> Option<f64> {
    let s = s.trim_start_matches(is_js_whitespace);
    let (negative, unsigned) = match s.as_bytes().first() {
        Some(b'-') => (true, &s[1..]),
        Some(b'+') => (false, &s[1..]),
        _ => (false, s),
    };
    let len = unsigned.bytes().take_while(u8::is_ascii_digit).count();
    let magnitude: f64 = unsigned[..len].parse().ok()?;
    Some(if negative { -magnitude } else { magnitude })
}

/// ECMAScript `Number::toString(x)` (radix 10), the text `String(x)` produces.
pub(crate) fn js_number_to_string(x: f64) -> String {
    if x.is_nan() {
        return "NaN".to_owned();
    }
    if x == 0.0 {
        return "0".to_owned();
    }
    if x.is_infinite() {
        return if x > 0.0 { "Infinity" } else { "-Infinity" }.to_owned();
    }
    let sign = if x < 0.0 { "-" } else { "" };
    // `{:e}` prints the shortest round-trip digits, the same digits ECMAScript picks.
    let sci = format!("{:e}", x.abs());
    let (mantissa, exponent) = sci
        .split_once('e')
        .expect("LowerExp output contains an exponent");
    let digits = mantissa.replace('.', "");
    let k = digits.len() as i32;
    let n = exponent
        .parse::<i32>()
        .expect("LowerExp exponent is an integer")
        + 1;
    let body = if k <= n && n <= 21 {
        digits + &"0".repeat((n - k) as usize)
    } else if 0 < n && n <= 21 {
        let (int, frac) = digits.split_at(n as usize);
        format!("{int}.{frac}")
    } else if -6 < n && n <= 0 {
        format!("0.{}{digits}", "0".repeat(-n as usize))
    } else {
        let e = n - 1;
        let e_sign = if e < 0 { '-' } else { '+' };
        let (first, rest) = digits.split_at(1);
        let point = if rest.is_empty() { "" } else { "." };
        format!("{first}{point}{rest}e{e_sign}{}", e.abs())
    };
    format!("{sign}{body}")
}

/// ECMAScript `WhiteSpace` and `LineTerminator`: what `\s`, `trim()` and `parseInt` skip.
pub(crate) fn is_js_whitespace(c: char) -> bool {
    const SINGLES: [char; 14] = [
        '\t', '\n', '\u{000B}', '\u{000C}', '\r', ' ', '\u{00A0}', '\u{1680}', '\u{2028}',
        '\u{2029}', '\u{202F}', '\u{205F}', '\u{3000}', '\u{FEFF}',
    ];
    SINGLES.contains(&c) || ('\u{2000}'..='\u{200A}').contains(&c)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cmp::Ordering::{Equal, Greater, Less};

    type Groups<'a> = [Option<&'a str>; 5];

    fn groups(version: &str) -> Option<Groups<'_>> {
        match_semver(version).map(|m| {
            let [major, minor, patch, fourth] = m.segments;
            [major, minor, patch, fourth, m.prerelease]
        })
    }

    fn cmp(a: &[&str], b: &[&str]) -> Ordering {
        compare_segments(a.iter().copied().map(Some), b.iter().copied().map(Some))
    }

    /// Expected groups recorded with Node 24 from the source regex.
    /// [ref: edge-cv-prefix-mixed-run] [ref: edge-cv-prefix-upper-v] [ref: edge-cv-upper-wildcard]
    /// [ref: edge-cv-build-upper] [ref: test/compare.ts::L56]
    #[test]
    fn semver_groups_match_the_source_regex() {
        let cases: &[(&str, Groups)] = &[
            ("1", [Some("1"), None, None, None, None]),
            ("1.2", [Some("1"), Some("2"), None, None, None]),
            (
                "v1.2.3.4-alpha.1+build.5",
                [Some("1"), Some("2"), Some("3"), Some("4"), Some("alpha.1")],
            ),
            ("1.x.X", [Some("1"), Some("x"), Some("X"), None, None]),
            ("1.*", [Some("1"), Some("*"), None, None, None]),
            (
                ">=~^v1.2.3-RC-1",
                [Some("1"), Some("2"), Some("3"), None, Some("RC-1")],
            ),
            (
                "1.2.3-x",
                [Some("1"), Some("2"), Some("3"), None, Some("x")],
            ),
            (
                "1.2.x-beta",
                [Some("1"), Some("2"), Some("x"), None, Some("beta")],
            ),
            ("V1.0.0", [Some("1"), Some("0"), Some("0"), None, None]),
            (
                "1.0.0.x-rc.0+B-1",
                [Some("1"), Some("0"), Some("0"), Some("x"), Some("rc.0")],
            ),
            (
                "01.002.0003",
                [Some("01"), Some("002"), Some("0003"), None, None],
            ),
            (
                "1.0.0--",
                [Some("1"), Some("0"), Some("0"), None, Some("-")],
            ),
            (
                "1.0.0-0.-.a",
                [Some("1"), Some("0"), Some("0"), None, Some("0.-.a")],
            ),
            ("1.2.3+build", [Some("1"), Some("2"), Some("3"), None, None]),
            (
                "1.2.3.4",
                [Some("1"), Some("2"), Some("3"), Some("4"), None],
            ),
            (
                "1.0.0-k",
                [Some("1"), Some("0"), Some("0"), None, Some("k")],
            ),
        ];
        for (input, expected) in cases {
            assert_eq!(groups(input), Some(*expected), "{input:?}");
        }
    }

    /// Inputs the source regex rejects (Node 24).
    /// [ref: ref-compare-L161] [ref: ref-compare-L162] [ref: ref-compare-L163] [ref: edge-cv-empty-v1]
    /// [ref: edge-cv-trailing-newline] [ref: edge-cv-five-segments]
    /// [ref: edge-cv-prerelease-needs-three-segments] [ref: edge-cv-build-needs-three-segments]
    /// [ref: edge-cv-empty-identifier] [ref: edge-cv-wildcard-first-segment] [ref: edge-cv-prefix-bang]
    /// [ref: edge-cv-unicode-arabic-indic-digits] [ref: edge-cv-unicode-kelvin-sign]
    /// [ref: edge-cv-unicode-long-s] [ref: edge-cv-unicode-dotless-i] [ref: edge-cv-unicode-fullwidth-v]
    #[test]
    fn semver_rejects_what_the_source_regex_rejects() {
        let rejected = [
            "",
            " 1.0.0",
            "1.0.0 ",
            "1.0.0\n",
            "1.0-alpha",
            "1-alpha",
            "1.0+build",
            "1.0.0-",
            "1.0.0+",
            "1.0.0-a..b",
            "1.0.0-*",
            "x",
            "*",
            "x.1.0",
            "1.0.0.0.0",
            "!1.0.0",
            "ver1.0.0",
            "v 1.0.0",
            "1.2.3a",
            "6.3.",
            "1.2.-3a",
            "\u{0661}.\u{0660}.\u{0660}",
            "1\u{0661}.0.0",
            "\u{FF11}.\u{FF12}.\u{FF13}",
            "1.0.0-\u{00E9}",
            "1.0.0-\u{212A}",
            "1.0.0-\u{017F}",
            "1.0.0-\u{0131}",
            "\u{FF56}1.0.0",
            "1.0.0+\u{00E9}",
            "1.xx",
            "1.x5",
            "1.0.0-rc+",
            "1.0.0+a.",
            "1.0.0-a.",
            "1.0.0-.a",
            "1.0.0-a_b",
            "v",
            "1..2",
            "1.2.3.4.x",
            "1.2.3-a+b+c",
        ];
        for input in rejected {
            assert_eq!(groups(input), None, "{input:?}");
        }
    }

    /// [ref: ref-compare-L161] [ref: edge-cv-message-quote] [ref: edge-cv-message-newline]
    /// [ref: edge-cv-message-unicode] [ref: edge-cv-empty-v1]
    #[test]
    fn validate_and_parse_reports_the_input_in_the_source_message() {
        let cases = [
            (
                "6.3.",
                "Invalid argument not valid semver ('6.3.' received)",
            ),
            (
                "1.0.0'x",
                "Invalid argument not valid semver ('1.0.0'x' received)",
            ),
            (
                "a\nb",
                "Invalid argument not valid semver ('a\nb' received)",
            ),
            (
                "\u{00FC}",
                "Invalid argument not valid semver ('\u{00FC}' received)",
            ),
            ("", "Invalid argument not valid semver ('' received)"),
        ];
        for (input, message) in cases {
            let err = validate_and_parse(input).unwrap_err();
            assert_eq!(err, Error::InvalidVersion(input.to_owned()));
            assert_eq!(err.to_string(), message);
        }
        assert!(validate_and_parse("1.0.0").is_ok());
    }

    /// [ref: ref-compare-L264] [ref: ref-compare-L265] [ref: ref-compare-L266]
    /// [ref: edge-cmp-invalid-op-eqeq] [ref: edge-cmp-invalid-op-ltgt] [ref: edge-cmp-invalid-op-eqgt]
    /// [ref: edge-cmp-invalid-op-leading-space]
    #[test]
    fn operator_parsing_and_message() {
        let all = [
            CompareOperator::Greater,
            CompareOperator::GreaterOrEqual,
            CompareOperator::Equal,
            CompareOperator::LessOrEqual,
            CompareOperator::Less,
            CompareOperator::NotEqual,
        ];
        for op in all {
            assert_eq!(op.to_string().parse::<CompareOperator>(), Ok(op));
        }
        let listed: Vec<String> = all.iter().map(ToString::to_string).collect();
        assert_eq!(listed.join("|"), ">|>=|=|<=|<|!=");
        for bad in [
            "", "foo", "> ", " >", "==", "===", "<>", "!", "=>", "=<", "gt",
        ] {
            assert_eq!(
                bad.parse::<CompareOperator>(),
                Err(Error::InvalidOperator),
                "{bad:?}"
            );
        }
        assert_eq!(
            Error::InvalidOperator.to_string(),
            "Invalid operator, expected one of >|>=|=|<=|<|!="
        );
    }

    /// Expected values recorded with Node 24 (`parseInt(s, 10)`).
    #[test]
    fn parse_int_reads_the_js_prefix() {
        let cases = [
            ("10a", Some(10.0)),
            ("-5", Some(-5.0)),
            ("0x10", Some(0.0)),
            ("abc", None),
            ("  12x", Some(12.0)),
            ("\t\n\u{000B}\u{000C}\r 7", Some(7.0)),
            (
                "\u{00A0}\u{1680}\u{2000}\u{200A}\u{2028}\u{2029}\u{202F}\u{205F}\u{3000}\u{FEFF}8",
                Some(8.0),
            ),
            ("\u{180E}9", None),
            ("\u{200B}9", None),
            ("+3", Some(3.0)),
            ("+", None),
            ("-", None),
            ("", None),
            ("1e3", Some(1.0)),
            ("1.5", Some(1.0)),
            ("0012", Some(12.0)),
            ("1_000", Some(1.0)),
            ("\u{FF11}", None),
        ];
        for (input, expected) in cases {
            assert_eq!(parse_int(input), expected, "{input:?}");
        }
        let negative_zero = parse_int("-0").unwrap();
        assert!(negative_zero == 0.0 && negative_zero.is_sign_negative());
    }

    /// [ref: edge-cv-2pow53-major] [ref: edge-cv-u64-overflow] [ref: edge-cv-1e308-vs-infinity]
    /// [ref: edge-cv-infinity-equal]
    #[test]
    fn parse_int_rounds_to_f64_and_overflows_to_infinity() {
        assert_eq!(parse_int("9007199254740993"), Some(9007199254740992.0));
        assert_eq!(parse_int("9007199254740995"), Some(9007199254740996.0));
        assert_eq!(
            parse_int("18446744073709551616"),
            Some(18446744073709551616.0)
        );
        assert_eq!(
            parse_int(&format!("1{}", "0".repeat(308))),
            Some(1e308),
            "309 digits"
        );
        assert_eq!(
            parse_int(&format!("1{}", "0".repeat(309))),
            Some(f64::INFINITY),
            "310 digits"
        );
        assert_eq!(parse_int(&"9".repeat(309)), Some(f64::INFINITY));
        assert_eq!(
            parse_int(&format!("-{}", "9".repeat(400))),
            Some(f64::NEG_INFINITY)
        );
    }

    /// Expected values recorded with Node 24 (`String(x)`).
    #[test]
    fn number_to_string_matches_js() {
        let cases = [
            (0.0, "0"),
            (-0.0, "0"),
            (f64::INFINITY, "Infinity"),
            (f64::NEG_INFINITY, "-Infinity"),
            (f64::NAN, "NaN"),
            (1.0, "1"),
            (-1.0, "-1"),
            (123.0, "123"),
            (1e20, "100000000000000000000"),
            (1e21, "1e+21"),
            (123456789012345680000.0, "123456789012345680000"),
            (1.2345e25, "1.2345e+25"),
            (9007199254740992.0, "9007199254740992"),
            (9007199254740994.0, "9007199254740994"),
            (18446744073709551616.0, "18446744073709552000"),
            (1e308, "1e+308"),
            (f64::MAX, "1.7976931348623157e+308"),
            (0.5, "0.5"),
            (1.5e-7, "1.5e-7"),
            (1e-7, "1e-7"),
            (0.000001, "0.000001"),
            (0.0000015, "0.0000015"),
            (1.23e-18, "1.23e-18"),
            (123.456, "123.456"),
            (-1.5e-7, "-1.5e-7"),
            (5e-324, "5e-324"),
            (1e100, "1e+100"),
        ];
        for (x, expected) in cases {
            assert_eq!(js_number_to_string(x), expected, "{x:e}");
        }
    }

    #[test]
    fn whitespace_is_the_ecmascript_set() {
        for c in [
            '\t', '\n', '\u{000B}', '\u{000C}', '\r', ' ', '\u{00A0}', '\u{1680}', '\u{2000}',
            '\u{2005}', '\u{200A}', '\u{2028}', '\u{2029}', '\u{202F}', '\u{205F}', '\u{3000}',
            '\u{FEFF}',
        ] {
            assert!(is_js_whitespace(c), "{c:?}");
        }
        for c in [
            'a', '0', '\u{0085}', '\u{180E}', '\u{200B}', '\u{1FFF}', '\u{200C}',
        ] {
            assert!(!is_js_whitespace(c), "{c:?}");
        }
    }

    /// [ref: test/compare.ts::L129] [ref: test/compare.ts::L130] [ref: test/compare.ts::L133]
    /// [ref: test/compare.ts::L135] [ref: edge-cv-nontransitive-a] [ref: edge-cv-nontransitive-c]
    /// [ref: edge-cv-wildcard-then-missing] [ref: edge-cv-wildcard-fourth]
    #[test]
    fn wildcards_compare_equal_to_anything() {
        let three = [Some("3"), None, None, None];
        assert_eq!(
            compare_segments(three, [Some("3"), Some("x"), Some("x"), None]),
            Equal
        );
        assert_eq!(cmp(&["3", "3"], &["3", "x", "x"]), Equal);
        assert_eq!(cmp(&["3", "3", "3"], &["3", "X", "X"]), Equal);
        assert_eq!(cmp(&["3", "3", "3"], &["3", "*", "*"]), Equal);
        assert_eq!(cmp(&["1", "x"], &["1", "5"]), Equal);
        assert_eq!(cmp(&["1", "5"], &["1", "7"]), Less);
        assert_eq!(cmp(&["1", "2", "3"], &["1", "x"]), Greater);
        assert_eq!(cmp(&["1", "0", "0", "x"], &["1", "0", "0", "5"]), Equal);
        assert_eq!(cmp(&["x"], &["alpha"]), Equal);
    }

    /// [ref: test/compare.ts::L69] [ref: test/compare.ts::L50] [ref: edge-cv-missing-identifier-zero]
    /// [ref: edge-cv-missing-identifier-00] [ref: edge-cv-identifier-alpha-vs-missing]
    #[test]
    fn missing_or_empty_segments_read_as_zero() {
        assert_eq!(cmp(&["1", "0", "0"], &["1"]), Equal);
        assert_eq!(
            compare_segments(
                [Some("1"), Some("0"), Some("0"), Some("0")],
                [Some("1"), None]
            ),
            Equal
        );
        assert_eq!(cmp(&["alpha"], &["alpha", "0"]), Equal);
        assert_eq!(cmp(&["alpha"], &["alpha", "00"]), Equal);
        assert_eq!(cmp(&["alpha", "beta"], &["alpha"]), Greater);
        assert_eq!(compare_segments([Some("")], [Some("0")]), Equal);
        assert_eq!(compare_segments([Some("")], [Some("1")]), Less);
        assert_eq!(compare_segments([None], [Some("1")]), Less);
        assert_eq!(cmp(&[], &[]), Equal);
    }

    /// [ref: edge-cv-parseint-prefix-equal] [ref: edge-cv-parseint-prefix-gt]
    /// [ref: edge-cv-parseint-numeric-vs-alnum] [ref: edge-cv-parseint-hyphenated]
    /// [ref: edge-cv-parseint-hex-like] [ref: edge-cv-parseint-exponent-like]
    /// [ref: edge-cv-leading-zeros-long] [ref: test/compare.ts::L82]
    #[test]
    fn segments_compare_by_their_parse_int_prefix() {
        assert_eq!(cmp(&["10a"], &["10b"]), Equal);
        assert_eq!(cmp(&["10a"], &["9"]), Greater);
        assert_eq!(cmp(&["11"], &["10a"]), Greater);
        assert_eq!(cmp(&["11"], &["1a"]), Greater);
        assert_eq!(cmp(&["1-2"], &["1-3"]), Equal);
        assert_eq!(cmp(&["0x10"], &["0"]), Equal);
        assert_eq!(cmp(&["1e3"], &["2"]), Less);
        assert_eq!(cmp(&["00000000000000000000001"], &["1"]), Equal);
        assert_eq!(cmp(&["beta", "2"], &["beta", "11"]), Less);
    }

    /// [ref: edge-cv-mixed-alpha-vs-number] [ref: edge-cv-mixed-number-vs-alpha]
    /// [ref: edge-cv-negative-identifier] [ref: edge-cv-negative-identifiers-order]
    /// [ref: edge-cv-negative-subidentifier] [ref: edge-cv-hyphen-string-vs-letter]
    /// [ref: edge-cv-prerelease-case-order] [ref: edge-cv-prerelease-upper-before-lower]
    #[test]
    fn numbers_against_strings_compare_as_js_strings() {
        assert_eq!(cmp(&["alpha"], &["10"]), Greater);
        assert_eq!(cmp(&["10"], &["alpha"]), Less);
        assert_eq!(cmp(&["-5"], &["0"]), Less);
        assert_eq!(cmp(&["-5"], &["-10"]), Greater);
        assert_eq!(cmp(&["alpha", "-1"], &["alpha"]), Less);
        assert_eq!(cmp(&["-a"], &["a"]), Less);
        assert_eq!(cmp(&["RC", "1"], &["rc", "1"]), Less);
        assert_eq!(cmp(&["Beta"], &["alpha"]), Less);
    }

    /// [ref: edge-cv-tostring-negative-zero] [ref: edge-cv-tostring-zero-vs-hyphen]
    /// [ref: edge-cv-tostring-infinity-vs-upper] [ref: edge-cv-tostring-infinity-vs-lower]
    /// [ref: edge-cv-tostring-finite-vs-upper] [ref: edge-cv-tostring-neg-infinity-vs-upper]
    /// [ref: edge-cv-tostring-exponent-vs-letter]
    #[test]
    fn number_text_follows_js_string_conversion() {
        let huge = "9".repeat(400);
        let negative_huge = format!("-{huge}");
        assert_eq!(cmp(&["-0"], &["-a"]), Greater);
        assert_eq!(cmp(&["0"], &["-a"]), Greater);
        assert_eq!(cmp(&[&huge], &["Alpha"]), Greater);
        assert_eq!(cmp(&[&huge], &["alpha"]), Less);
        assert_eq!(cmp(&["99999999999999999999"], &["Alpha"]), Less);
        assert_eq!(cmp(&[&negative_huge], &["-A"]), Greater);
        assert_eq!(cmp(&["1000000000000000000000"], &["e"]), Less);
    }

    /// [ref: edge-cv-2pow53-major] [ref: edge-cv-2pow53-exact-step] [ref: edge-cv-2pow53-below]
    /// [ref: edge-cv-u64-overflow] [ref: edge-cv-u64-max-vs-small] [ref: edge-cv-infinity-equal]
    /// [ref: edge-cv-infinity-vs-one] [ref: edge-cv-1e308-vs-infinity]
    #[test]
    fn numeric_segments_compare_as_f64() {
        let huge = "9".repeat(400);
        let huge_minus_one = format!("{}8", "9".repeat(399));
        let e308 = format!("1{}", "0".repeat(308));
        let e309 = format!("1{}", "0".repeat(309));
        assert_eq!(cmp(&["9007199254740993"], &["9007199254740992"]), Equal);
        assert_eq!(cmp(&["9007199254740994"], &["9007199254740992"]), Greater);
        assert_eq!(cmp(&["9007199254740991"], &["9007199254740990"]), Greater);
        assert_eq!(
            cmp(&["18446744073709551616"], &["18446744073709551615"]),
            Equal
        );
        assert_eq!(cmp(&["18446744073709551615"], &["1"]), Greater);
        assert_eq!(cmp(&[&huge], &[&huge_minus_one]), Equal);
        assert_eq!(cmp(&[&huge], &["1"]), Greater);
        assert_eq!(cmp(&[&e308], &[&e309]), Less);
    }
}
