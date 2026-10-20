//! Python's `str.isupper`, `str.isnumeric` and `repr(float)`, matched to CPython 3.14 (Unicode 16).

use crate::unicode_tables::{
    LOWER_MAP_PY, LOWER_PY_ONLY, LOWER_STD_ONLY, NUMERIC_PY_ONLY, NUMERIC_STD_ONLY, TITLECASE,
    UPPER_MAP_PY, UPPER_PY_ONLY, UPPER_STD_ONLY,
};
use std::cmp::Ordering;

fn in_table(table: &[(char, char)], c: char) -> bool {
    table
        .binary_search_by(|&(lo, hi)| {
            if hi < c {
                Ordering::Less
            } else if lo > c {
                Ordering::Greater
            } else {
                Ordering::Equal
            }
        })
        .is_ok()
}

fn adjusted(std: bool, c: char, std_only: &[(char, char)], py_only: &[(char, char)]) -> bool {
    if std {
        !in_table(std_only, c)
    } else {
        in_table(py_only, c)
    }
}

fn is_upper(c: char) -> bool {
    adjusted(c.is_uppercase(), c, UPPER_STD_ONLY, UPPER_PY_ONLY)
}

fn is_lower(c: char) -> bool {
    adjusted(c.is_lowercase(), c, LOWER_STD_ONLY, LOWER_PY_ONLY)
}

fn is_numeric(c: char) -> bool {
    adjusted(c.is_numeric(), c, NUMERIC_STD_ONLY, NUMERIC_PY_ONLY)
}

/// `str.isupper`: at least one uppercase character and no lowercase or titlecase one.
pub(crate) fn py_isupper(s: &str) -> bool {
    let mut cased = false;
    for c in s.chars() {
        if is_lower(c) || in_table(TITLECASE, c) {
            return false;
        }
        cased |= is_upper(c);
    }
    cased
}

/// `str.isnumeric`: non-empty and every character has a Numeric_Type.
pub(crate) fn py_isnumeric(s: &str) -> bool {
    !s.is_empty() && s.chars().all(is_numeric)
}

fn mapped(table: &'static [(char, &'static str)], c: char) -> Option<&'static str> {
    table
        .binary_search_by_key(&c, |&(k, _)| k)
        .ok()
        .map(|i| table[i].1)
}

/// `c.upper()`: std's full mapping, except where CPython 3.14 (Unicode 16) maps differently.
pub(crate) fn py_upper_char(c: char, out: &mut String) {
    match mapped(UPPER_MAP_PY, c) {
        Some(py) => out.push_str(py),
        None => out.extend(c.to_uppercase()),
    }
}

/// `c.lower()` for a single character (no Final_Sigma context, as in Python).
pub(crate) fn py_lower_char(c: char, out: &mut String) {
    match mapped(LOWER_MAP_PY, c) {
        Some(py) => out.push_str(py),
        None => out.extend(c.to_lowercase()),
    }
}

/// `s.lower()`: std's `to_lowercase` (which applies Final_Sigma) on the runs between characters CPython
/// maps differently.
pub(crate) fn py_lower(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut run_start = 0;
    for (i, c) in s.char_indices() {
        if let Some(py) = mapped(LOWER_MAP_PY, c) {
            // DIVERGENCE(unicode-version): Final_Sigma context uses std's Unicode 17 Cased and
            // Case_Ignorable sets, so a sigma next to a character whose casedness changed between
            // Unicode 16 and 17 (U+0295, or one of these runs) can lower differently from CPython 3.14.
            out.push_str(&s[run_start..i].to_lowercase());
            out.push_str(py);
            run_start = i + c.len_utf8();
        }
    }
    out.push_str(&s[run_start..].to_lowercase());
    out
}

/// `repr(f)` for a finite float.
///
/// The shortest round-trip digits, with exact ties rounded to even as CPython does (`{:e}` rounds them
/// up), laid out with Python's rules: exponent form below 1e-4 and from 1e16, written `e+16` / `e-05`.
pub(crate) fn py_float_repr(f: f64) -> String {
    let shortest = format!("{f:e}");
    let significant = shortest
        .split_once('e')
        .map_or(1, |(m, _)| m.chars().filter(char::is_ascii_digit).count());
    let even = format!("{:.*e}", significant.saturating_sub(1), f);
    let sci = if even.parse::<f64>() == Ok(f) {
        even
    } else {
        shortest
    };
    let (mantissa, exp) = sci.split_once('e').expect("{:e} output has an exponent");
    let exp: i32 = exp.parse().expect("{:e} exponent is an integer");
    let (sign, mantissa) = match mantissa.strip_prefix('-') {
        Some(m) => ("-", m),
        None => ("", mantissa),
    };
    let digits: String = mantissa.chars().filter(|&c| c != '.').collect();
    if !(-4..16).contains(&exp) {
        let (head, tail) = digits.split_at(1);
        let dot = if tail.is_empty() { "" } else { "." };
        let esign = if exp < 0 { '-' } else { '+' };
        format!("{sign}{head}{dot}{tail}e{esign}{:02}", exp.unsigned_abs())
    } else if exp < 0 {
        let zeros = "0".repeat(exp.unsigned_abs() as usize - 1);
        format!("{sign}0.{zeros}{digits}")
    } else {
        let point = exp as usize + 1;
        if digits.len() <= point {
            format!("{sign}{digits}{}.0", "0".repeat(point - digits.len()))
        } else {
            format!("{sign}{}.{}", &digits[..point], &digits[point..])
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn float_repr_exponent_thresholds() {
        let rows = [
            (1e16, "1e+16"),
            (9999999999999998.0, "9999999999999998.0"),
            (1.5e16, "1.5e+16"),
            (1e-4, "0.0001"),
            (1e-5, "1e-05"),
            (-1e-5, "-1e-05"),
            (1.234e-7, "1.234e-07"),
            (1e100, "1e+100"),
            (f64::MAX, "1.7976931348623157e+308"),
            (5e-324, "5e-324"),
            (1.0, "1.0"),
            (-2.5, "-2.5"),
            (0.0, "0.0"),
            (-0.0, "-0.0"),
            (0.1 + 0.2, "0.30000000000000004"),
            (1e15, "1000000000000000.0"),
            (966928176821182.0 + 0.25, "966928176821182.2"),
        ];
        for (f, want) in rows {
            assert_eq!(py_float_repr(f), want, "repr({f:e})");
        }
    }

    #[test]
    fn isupper_follows_python() {
        assert!(py_isupper("API"));
        assert!(py_isupper("_API_"));
        assert!(py_isupper("BIP73"));
        assert!(py_isupper("ẞ"));
        assert!(!py_isupper(""));
        assert!(!py_isupper("123"));
        assert!(!py_isupper("APi"));
        // Titlecase letters make the whole string not uppercase.
        assert!(!py_isupper("ǅ"));
        assert!(!py_isupper("AǅB"));
        // U+0295 is Ll in Unicode 16 (Python 3.14) and Lo in Unicode 17 (Rust std).
        assert!(!py_isupper("A\u{295}"));
        // U+A7CE is unassigned in Unicode 16.
        assert!(!py_isupper("\u{a7ce}"));
    }

    #[test]
    fn isnumeric_follows_python() {
        assert!(py_isnumeric("123"));
        assert!(py_isnumeric("三"));
        assert!(py_isnumeric("½²٣５ⅻ"));
        assert!(!py_isnumeric(""));
        assert!(!py_isnumeric("1.5"));
        assert!(!py_isnumeric("-5"));
        // New in Unicode 17, unassigned for Python 3.14.
        assert!(!py_isnumeric("\u{11de0}"));
    }
}
