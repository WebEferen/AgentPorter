use std::cmp::Ordering;

use crate::compare_versions::compare_versions;
use crate::utils::{CompareOperator, Error};

/// Compares two versions with one of `>`, `>=`, `=`, `<=`, `<`, `!=`.
///
/// ```
/// assert_eq!(compare_versions_port::compare("10.1.8", "10.0.4", ">"), Ok(true));
/// assert_eq!(compare_versions_port::compare("10.1.1", "10.2.2", ">="), Ok(false));
/// ```
///
/// # Errors
///
/// [`Error::InvalidOperator`] for an unknown operator, checked before the versions, then
/// [`Error::InvalidVersion`].
// DIVERGENCE(non-string-arguments): the source's `typeof operator` guard has no counterpart;
// `&str` makes non-string input unrepresentable.
pub fn compare(v1: &str, v2: &str, operator: &str) -> Result<bool, Error> {
    let operator: CompareOperator = operator.parse()?;
    let res = compare_versions(v1, v2)?;
    Ok(match operator {
        CompareOperator::Greater => res == Ordering::Greater,
        CompareOperator::GreaterOrEqual => res != Ordering::Less,
        CompareOperator::Equal => res == Ordering::Equal,
        CompareOperator::LessOrEqual => res != Ordering::Greater,
        CompareOperator::Less => res == Ordering::Less,
        CompareOperator::NotEqual => res != Ordering::Equal,
    })
}
