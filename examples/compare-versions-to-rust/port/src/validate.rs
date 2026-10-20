use crate::utils::match_semver;

/// Whether `version` is a version string the loose parser accepts: it starts with `v` or a digit
/// and matches the shared semver pattern (1 to 4 segments, `x`/`X`/`*` wildcards after the first).
///
/// ```
/// assert!(compare_versions_port::validate("1.0.0-rc.1"));
/// assert!(!compare_versions_port::validate("1.0-rc.1"));
/// assert!(!compare_versions_port::validate("foo"));
/// ```
// DIVERGENCE(non-string-arguments): the source returns false for non-string input; `&str` makes
// that unrepresentable, so the `typeof` guard is dropped.
pub fn validate(version: &str) -> bool {
    matches!(version.as_bytes().first(), Some(b'v' | b'0'..=b'9'))
        && match_semver(version).is_some()
}

/// Whether `version` is a valid semver.org 2.0.0 version: exactly three numeric segments without
/// leading zeros, an optional pre-release and optional build metadata. Wildcards and ranges are
/// rejected.
///
/// ```
/// assert!(compare_versions_port::validate_strict("1.0.0-rc.1"));
/// assert!(!compare_versions_port::validate_strict("1.0-rc.1"));
/// ```
// DIVERGENCE(non-string-arguments): see `validate`.
pub fn validate_strict(version: &str) -> bool {
    let mut rest = version;
    for _ in 0..2 {
        if !(take_numeric(&mut rest) && take_char(&mut rest, '.')) {
            return false;
        }
    }
    if !take_numeric(&mut rest) {
        return false;
    }
    if take_char(&mut rest, '-') && !take_list(&mut rest, is_prerelease_identifier) {
        return false;
    }
    if take_char(&mut rest, '+') && !take_list(&mut rest, |_| true) {
        return false;
    }
    rest.is_empty()
}

fn take_char(rest: &mut &str, c: char) -> bool {
    match rest.strip_prefix(c) {
        Some(tail) => {
            *rest = tail;
            true
        }
        None => false,
    }
}

/// `0|[1-9]\d*`
fn take_numeric(rest: &mut &str) -> bool {
    let len = rest.bytes().take_while(u8::is_ascii_digit).count();
    if len == 0 || (len > 1 && rest.starts_with('0')) {
        return false;
    }
    *rest = &rest[len..];
    true
}

/// `[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*`, each identifier also accepted by `accept`.
fn take_list(rest: &mut &str, accept: impl Fn(&str) -> bool) -> bool {
    loop {
        let len = rest
            .bytes()
            .take_while(|b| b.is_ascii_alphanumeric() || *b == b'-')
            .count();
        if len == 0 || !accept(&rest[..len]) {
            return false;
        }
        *rest = &rest[len..];
        if !take_char(rest, '.') {
            return true;
        }
    }
}

/// `0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*` over an identifier already known to be `[0-9a-zA-Z-]+`:
/// only an all-digit identifier with a leading zero is rejected.
fn is_prerelease_identifier(id: &str) -> bool {
    !(id.len() > 1 && id.starts_with('0') && id.bytes().all(|b| b.is_ascii_digit()))
}
