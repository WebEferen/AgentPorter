//! Compare [semver](https://semver.org/) version strings with the rules of the
//! [`compare-versions`](https://www.npmjs.com/package/compare-versions) npm package (6.1.1),
//! quirks included.
//!
//! Every function takes `&str`. The source also handles non-string arguments (`validate` returns
//! `false`, the others throw a `TypeError`); those cases cannot be expressed here
//! (divergence `non-string-arguments`).
//!
//! Quirks kept from the original: [`validate`] is loose (wildcards and 1 to 4 segments pass,
//! [`validate_strict`] is the semver.org grammar), segments and pre-release identifiers compare by
//! their JavaScript `parseInt` prefix (a number against a non-numeric string compares as strings), build metadata is ignored, and [`satisfies`] evaluates `||` alternatives
//! and comparator sets lazily, so an invalid part after the deciding one is never reported.
//!
//! ```
//! use std::cmp::Ordering;
//! use compare_versions_port::{compare, compare_versions, satisfies, validate, validate_strict};
//!
//! assert_eq!(compare_versions("1.0.0-alpha", "1.0.0"), Ok(Ordering::Less));
//! assert_eq!(compare("10.1.8", "10.0.4", ">"), Ok(true));
//! assert_eq!(satisfies("1.1.0", "^1.0.0"), Ok(true));
//! assert!(validate("1.0.x"));
//! assert!(!validate_strict("1.0.x"));
//! assert!(compare("1.0.0", "1.0.0", "~").is_err());
//! ```

mod compare;
mod compare_versions;
mod satisfies;
mod utils;
mod validate;

pub use compare::compare;
pub use compare_versions::compare_versions;
pub use satisfies::satisfies;
pub use utils::{CompareOperator, Error};
pub use validate::{validate, validate_strict};
