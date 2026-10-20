use compare_versions_port::compare_versions;

fn sorted(mut versions: Vec<&str>) -> Vec<&str> {
    versions.sort_by(|a, b| compare_versions(a, b).unwrap());
    versions
}

// [ref: test/sort.ts::L5]
#[test]
fn sorts_versions() {
    let versions = vec![
        "1.2.3", "4.11.6", "4.2.0", "1.5.19", "1.5.5", "4.1.3", "2.3.1", "10.5.5", "11.3.0",
    ];
    assert_eq!(
        sorted(versions),
        ["1.2.3", "1.5.5", "1.5.19", "2.3.1", "4.1.3", "4.2.0", "4.11.6", "10.5.5", "11.3.0"]
    );
}

// [ref: test/sort.ts::L31]
#[test]
fn sorts_different_digits() {
    assert_eq!(
        sorted(vec!["1.0", "1.0.0", "1.0.1"]),
        ["1.0", "1.0.0", "1.0.1"]
    );
}

// [ref: test/sort.ts::L37]
#[test]
fn sorts_pre_release() {
    assert_eq!(
        sorted(vec!["1.0.0", "1.0.1", "1.0.1-gamma", "1.0.1-alpha"]),
        ["1.0.0", "1.0.1-alpha", "1.0.1-gamma", "1.0.1"]
    );
}
