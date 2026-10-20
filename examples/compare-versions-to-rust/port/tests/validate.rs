use compare_versions_port::{validate, validate_strict};

/// [ref: test/validate.ts::L13]
/// [ref: test/validate.ts::L14]
/// [ref: test/validate.ts::L15]
/// [ref: test/validate.ts::L16]
/// [ref: test/validate.ts::L26]
/// [ref: test/validate.ts::L27]
#[test]
fn validate_rejects_malformed_versions() {
    for version in ["foo", "6.3.", "1.2.3a", "1.2.-3a", "=1.0", ">1.0.0"] {
        assert!(!validate(version), "{version:?}");
    }
}

/// [ref: test/validate.ts::L17]
/// [ref: test/validate.ts::L18]
/// [ref: test/validate.ts::L19]
/// [ref: test/validate.ts::L20]
/// [ref: test/validate.ts::L21]
/// [ref: test/validate.ts::L22]
/// [ref: test/validate.ts::L23]
/// [ref: test/validate.ts::L24]
/// [ref: test/validate.ts::L25]
#[test]
fn validate_accepts_loose_versions() {
    for version in [
        "v1.0.0",
        "01.0.0",
        "1.0.x",
        "1.0.0-rc.1",
        "1.0.0-alpha",
        "1.0.0-build.3928",
        "1.0.0+20130313144700",
        "1.2.3.100",
        "2020",
    ] {
        assert!(validate(version), "{version:?}");
    }
}

/// [ref: test/validate.ts::L39]
/// [ref: test/validate.ts::L40]
/// [ref: test/validate.ts::L41]
/// [ref: test/validate.ts::L42]
/// [ref: test/validate.ts::L43]
/// [ref: test/validate.ts::L44]
/// [ref: test/validate.ts::L45]
/// [ref: test/validate.ts::L46]
/// [ref: test/validate.ts::L47]
/// [ref: test/validate.ts::L48]
/// [ref: test/validate.ts::L49]
/// [ref: test/validate.ts::L50]
/// [ref: test/validate.ts::L51]
/// [ref: test/validate.ts::L52]
/// [ref: test/validate.ts::L53]
/// [ref: test/validate.ts::L54]
/// [ref: test/validate.ts::L55]
/// [ref: test/validate.ts::L56]
/// [ref: test/validate.ts::L57]
/// [ref: test/validate.ts::L58]
/// [ref: test/validate.ts::L59]
/// [ref: test/validate.ts::L60]
/// [ref: test/validate.ts::L61]
/// [ref: test/validate.ts::L62]
/// [ref: test/validate.ts::L63]
/// [ref: test/validate.ts::L64]
/// [ref: test/validate.ts::L65]
/// [ref: test/validate.ts::L66]
/// [ref: test/validate.ts::L67]
/// [ref: test/validate.ts::L68]
/// [ref: test/validate.ts::L69]
#[test]
fn validate_strict_accepts_valid_semver() {
    for version in [
        "0.0.4",
        "1.2.3",
        "10.20.30",
        "1.1.2-prerelease+meta",
        "1.1.2+meta",
        "1.1.2+meta-valid",
        "1.0.0-alpha",
        "1.0.0-beta",
        "1.0.0-alpha.beta",
        "1.0.0-alpha.beta.1",
        "1.0.0-alpha.1",
        "1.0.0-alpha0.valid",
        "1.0.0-alpha.0valid",
        "1.0.0-alpha-a.b-c-somethinglong+build.1-aef.1-its-okay",
        "1.0.0-rc.1+build.1",
        "2.0.0-rc.1+build.123",
        "1.2.3-beta",
        "10.2.3-DEV-SNAPSHOT",
        "1.2.3-SNAPSHOT-123",
        "1.0.0",
        "2.0.0",
        "1.1.7",
        "2.0.0+build.1848",
        "2.0.1-alpha.1227",
        "1.0.0-alpha+beta",
        "1.2.3----RC-SNAPSHOT.12.9.1--.12+788",
        "1.2.3----R-S.12.9.1--.12+meta",
        "1.2.3----RC-SNAPSHOT.12.9.1--.12",
        "1.0.0+0.build.1-rc.10000aaa-kk-0.1",
        "99999999999999999999999.999999999999999999.99999999999999999",
        "1.0.0-0A.is.legal",
    ] {
        assert!(validate_strict(version), "{version:?}");
    }
}

/// [ref: test/validate.ts::L79]
/// [ref: test/validate.ts::L80]
/// [ref: test/validate.ts::L81]
/// [ref: test/validate.ts::L82]
/// [ref: test/validate.ts::L83]
/// [ref: test/validate.ts::L84]
/// [ref: test/validate.ts::L85]
/// [ref: test/validate.ts::L86]
/// [ref: test/validate.ts::L87]
/// [ref: test/validate.ts::L88]
/// [ref: test/validate.ts::L89]
/// [ref: test/validate.ts::L90]
/// [ref: test/validate.ts::L91]
/// [ref: test/validate.ts::L92]
/// [ref: test/validate.ts::L93]
/// [ref: test/validate.ts::L94]
/// [ref: test/validate.ts::L95]
/// [ref: test/validate.ts::L96]
/// [ref: test/validate.ts::L97]
/// [ref: test/validate.ts::L98]
/// [ref: test/validate.ts::L99]
/// [ref: test/validate.ts::L100]
/// [ref: test/validate.ts::L101]
/// [ref: test/validate.ts::L102]
/// [ref: test/validate.ts::L103]
/// [ref: test/validate.ts::L104]
/// [ref: test/validate.ts::L105]
/// [ref: test/validate.ts::L106]
/// [ref: test/validate.ts::L107]
/// [ref: test/validate.ts::L108]
/// [ref: test/validate.ts::L109]
/// [ref: test/validate.ts::L110]
/// [ref: test/validate.ts::L111]
/// [ref: test/validate.ts::L112]
/// [ref: test/validate.ts::L113]
/// [ref: test/validate.ts::L114]
/// [ref: test/validate.ts::L115]
/// [ref: test/validate.ts::L116]
/// [ref: test/validate.ts::L117]
/// [ref: test/validate.ts::L118]
/// [ref: test/validate.ts::L119]
#[test]
fn validate_strict_rejects_invalid_semver() {
    for version in [
        "1",
        "1.2",
        "1.2.3-0123",
        "1.2.3-0123.0123",
        "1.1.2+.123",
        "+invalid",
        "-invalid",
        "-invalid+invalid",
        "-invalid.01",
        "alpha",
        "alpha.beta",
        "alpha.beta.1",
        "alpha.1",
        "alpha+beta",
        "alpha_beta",
        "alpha.",
        "alpha..",
        "beta",
        "1.0.0-alpha_beta",
        "-alpha.",
        "1.0.0-alpha..",
        "1.0.0-alpha..1",
        "1.0.0-alpha...1",
        "1.0.0-alpha....1",
        "1.0.0-alpha.....1",
        "1.0.0-alpha......1",
        "1.0.0-alpha.......1",
        "01.1.1",
        "1.01.1",
        "1.1.01",
        "1.2",
        "1.2.3.DEV",
        "1.2-SNAPSHOT",
        "1.2.31.2.3----RC-SNAPSHOT.12.09.1--..12+788",
        "1.2-RC-SNAPSHOT",
        "-1.0.3-gamma+b7718",
        "+justmeta",
        "9.8.7+meta+meta",
        "9.8.7-whatever+meta+meta",
        "99999999999999999999999.999999999999999999.99999999999999999----RC-SNAPSHOT.12.09.1--------------------------------..",
        "12",
    ] {
        assert!(!validate_strict(version), "{version:?}");
    }
}
