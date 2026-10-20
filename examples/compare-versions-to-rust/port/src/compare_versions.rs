use std::cmp::Ordering;

use crate::utils::{compare_segments, validate_and_parse, Error};

/// Compares two versions: the numeric segments first, then the pre-release. A version with a
/// pre-release is lower than the same version without one. Build metadata is ignored.
///
/// ```
/// use std::cmp::Ordering;
/// assert_eq!(compare_versions_port::compare_versions("1.0.0-alpha", "1.0.0"), Ok(Ordering::Less));
/// ```
///
/// # Errors
///
/// [`Error::InvalidVersion`] for the first of `v1`, `v2` that is not a valid version.
pub fn compare_versions(v1: &str, v2: &str) -> Result<Ordering, Error> {
    let n1 = validate_and_parse(v1)?;
    let n2 = validate_and_parse(v2)?;

    let r = compare_segments(n1.segments, n2.segments);
    if r.is_ne() {
        return Ok(r);
    }

    Ok(match (n1.prerelease, n2.prerelease) {
        (Some(p1), Some(p2)) => compare_segments(p1.split('.').map(Some), p2.split('.').map(Some)),
        (Some(_), None) => Ordering::Less,
        (None, Some(_)) => Ordering::Greater,
        (None, None) => Ordering::Equal,
    })
}
