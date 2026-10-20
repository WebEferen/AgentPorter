use std::cmp::Ordering;

use crate::compare::compare;
use crate::utils::{compare_segments, is_js_whitespace, validate_and_parse, Error};

/// Whether `version` is within the npm-style `range`: comparators (`>`, `>=`, `=`, `<=`, `<`,
/// `!=`), `~` and `^` ranges, `a - b` hyphen ranges, space separated sets and `||` alternatives.
///
/// ```
/// assert_eq!(compare_versions_port::satisfies("1.1.0", "^1.0.0"), Ok(true));
/// assert_eq!(compare_versions_port::satisfies("1.1.0", "~1.0.0"), Ok(false));
/// ```
///
/// # Errors
///
/// [`Error::InvalidVersion`] or [`Error::InvalidOperator`] for the first invalid part reached.
/// Alternatives and comparator sets are evaluated lazily, so parts after the deciding one are
/// never checked.
// DIVERGENCE(non-string-arguments): the source's `range.replace` throws a `TypeError` on a
// non-string range; `&str` makes that unrepresentable.
pub fn satisfies(version: &str, range: &str) -> Result<bool, Error> {
    let range = strip_space_after_operators(range);

    if range.contains("||") {
        for r in range.split("||") {
            if satisfies(version, r)? {
                return Ok(true);
            }
        }
        return Ok(false);
    } else if range.contains(" - ") {
        let mut parts = range.split(" - ");
        let a = parts.next().unwrap_or_default();
        let b = parts.next().unwrap_or_default();
        // JS `split(' - ', 2)` drops every piece after the second.
        return satisfies(version, &format!(">={a} <={b}"));
    } else if range.contains(' ') {
        let trimmed = range.trim_matches(is_js_whitespace);
        for r in collapse_whitespace(trimmed).split(' ') {
            if !satisfies(version, r)? {
                return Ok(false);
            }
        }
        return Ok(true);
    }

    let op_len = range
        .find(|c| !matches!(c, '<' | '>' | '=' | '~' | '^'))
        .unwrap_or(range.len());
    let op = if op_len == 0 { "=" } else { &range[..op_len] };

    if op != "^" && op != "~" {
        return compare(version, &range, op);
    }

    let v = validate_and_parse(version)?;
    let r = validate_and_parse(&range)?;
    let vs = [v.segments[0], v.segments[1], v.segments[2]];
    let rs = [
        r.segments[0],
        r.segments[1].or(Some("x")),
        r.segments[2].or(Some("x")),
    ];

    if let Some(rp) = r.prerelease {
        let Some(vp) = v.prerelease else {
            return Ok(false);
        };
        if compare_segments(vs, rs).is_ne() {
            return Ok(false);
        }
        if compare_segments(vp.split('.').map(Some), rp.split('.').map(Some)) == Ordering::Less {
            return Ok(false);
        }
    }

    let non_zero = rs.iter().position(|s| *s != Some("0")).map_or(0, |i| i + 1);
    let i = if op == "~" { 2 } else { non_zero.max(1) };

    if compare_segments(vs[..i].iter().copied(), rs[..i].iter().copied()).is_ne() {
        return Ok(false);
    }
    Ok(compare_segments(vs[i..].iter().copied(), rs[i..].iter().copied()) != Ordering::Less)
}

/// `range.replace(/([><=]+)\s+/g, '$1')`.
fn strip_space_after_operators(range: &str) -> String {
    let mut out = String::with_capacity(range.len());
    let mut chars = range.chars().peekable();
    while let Some(c) = chars.next() {
        out.push(c);
        if matches!(c, '<' | '>' | '=') {
            if matches!(chars.peek(), Some('<' | '>' | '=')) {
                continue;
            }
            while chars.next_if(|c| is_js_whitespace(*c)).is_some() {}
        }
    }
    out
}

/// `s.replace(/\s{2,}/g, ' ')`.
fn collapse_whitespace(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if is_js_whitespace(c) && chars.peek().is_some_and(|n| is_js_whitespace(*n)) {
            while chars.next_if(|n| is_js_whitespace(*n)).is_some() {}
            out.push(' ');
        } else {
            out.push(c);
        }
    }
    out
}
