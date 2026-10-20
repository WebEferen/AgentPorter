use std::cmp::Ordering;

use compare_versions_port::{
    compare, compare_versions, satisfies, validate, validate_strict, CompareOperator, Error,
};

// [ref: src/index.ts::L1]
// [ref: src/index.ts::L2]
// [ref: src/index.ts::L3]
// [ref: src/index.ts::L4]
// [ref: src/index.ts::L5]
#[test]
fn crate_root_exposes_every_public_name() {
    assert_eq!(compare_versions("1.0.0", "1.0.1"), Ok(Ordering::Less));
    assert_eq!(compare("1.0.1", "1.0.0", ">"), Ok(true));
    assert_eq!(satisfies("1.2.3", "^1.0.0"), Ok(true));
    assert!(validate("1.2.3"));
    assert!(validate_strict("1.2.3"));
    assert_eq!(
        ">=".parse::<CompareOperator>(),
        Ok(CompareOperator::GreaterOrEqual)
    );
    assert_eq!(compare("1.0.0", "1.0.0", "~"), Err(Error::InvalidOperator));
}

// [ref: src/index.ts::L1]
// [ref: src/index.ts::L2]
// [ref: src/index.ts::L3]
// [ref: src/index.ts::L5]
#[test]
fn harness_bindings_name_every_fixture_call_id() {
    let bindings = include_str!("../examples/porter_harness/bindings.rs");
    for id in [
        "compare-versions:compareVersions",
        "compare-versions:compare",
        "compare-versions:satisfies",
        "compare-versions:validate",
        "compare-versions:validateStrict",
    ] {
        assert!(bindings.contains(&format!("\"{id}\"")), "{id}");
    }
}
