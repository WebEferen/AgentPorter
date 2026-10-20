use compare_versions_port::{compare, compare_versions, Error};
use std::cmp::Ordering::{self, Equal, Greater, Less};

fn check(rows: &[(&str, &str, Ordering)]) {
    for &(v1, v2, expected) in rows {
        assert_eq!(compare_versions(v1, v2), Ok(expected), "{v1} {v2}");
    }
}

// [ref: test/compare.ts::L24]
// [ref: test/compare.ts::L25]
// [ref: test/compare.ts::L26]
#[test]
fn compare_versions_single_segment() {
    check(&[("10", "9", Greater), ("10", "10", Equal), ("9", "10", Less)]);
}

// [ref: test/compare.ts::L32]
// [ref: test/compare.ts::L33]
// [ref: test/compare.ts::L34]
#[test]
fn compare_versions_two_segment() {
    check(&[
        ("10.8", "10.4", Greater),
        ("10.1", "10.1", Equal),
        ("10.1", "10.2", Less),
    ]);
}

// [ref: test/compare.ts::L40]
// [ref: test/compare.ts::L41]
// [ref: test/compare.ts::L42]
// [ref: test/compare.ts::L43]
// [ref: test/compare.ts::L44]
#[test]
fn compare_versions_three_segment() {
    check(&[
        ("10.1.8", "10.0.4", Greater),
        ("10.0.1", "10.0.1", Equal),
        ("10.1.1", "10.2.2", Less),
        ("11.0.10", "11.0.2", Greater),
        ("11.0.2", "11.0.10", Less),
    ]);
}

// [ref: test/compare.ts::L50]
// [ref: test/compare.ts::L51]
// [ref: test/compare.ts::L52]
// [ref: test/compare.ts::L53]
// [ref: test/compare.ts::L54]
// [ref: test/compare.ts::L55]
// [ref: test/compare.ts::L56]
// [ref: test/compare.ts::L57]
// [ref: test/compare.ts::L58]
// [ref: test/compare.ts::L59]
// [ref: test/compare.ts::L60]
#[test]
fn compare_versions_four_segment() {
    check(&[
        ("1.0.0.0", "1", Equal),
        ("1.0.0.0", "1.0", Equal),
        ("1.0.0.0", "1.0.0", Equal),
        ("1.0.0.0", "1.0.0.0", Equal),
        ("1.2.3.4", "1.2.3.4", Equal),
        ("1.2.3.4", "1.2.3.04", Equal),
        ("v1.2.3.4", "01.2.3.4", Equal),
        ("1.2.3.4", "1.2.3.5", Less),
        ("1.2.3.5", "1.2.3.4", Greater),
        ("1.0.0.0-alpha", "1.0.0-alpha", Equal),
        ("1.0.0.0-alpha", "1.0.0.0-beta", Less),
    ]);
}

// [ref: test/compare.ts::L66]
// [ref: test/compare.ts::L67]
// [ref: test/compare.ts::L68]
// [ref: test/compare.ts::L69]
// [ref: test/compare.ts::L70]
// [ref: test/compare.ts::L71]
#[test]
fn compare_versions_different_segment() {
    check(&[
        ("11.1.10", "11.0", Greater),
        ("1.1.1", "1", Greater),
        ("01.1.0", "1.01", Equal),
        ("1.0.0", "1", Equal),
        ("10.0.0", "10.114", Less),
        ("1.0", "1.4.1", Less),
    ]);
}

// [ref: test/compare.ts::L77]
// [ref: test/compare.ts::L78]
// [ref: test/compare.ts::L79]
// [ref: test/compare.ts::L80]
// [ref: test/compare.ts::L81]
// [ref: test/compare.ts::L82]
// [ref: test/compare.ts::L83]
// [ref: test/compare.ts::L84]
// [ref: test/compare.ts::L85]
// [ref: test/compare.ts::L86]
// [ref: test/compare.ts::L87]
// [ref: test/compare.ts::L88]
#[test]
fn compare_versions_pre_release() {
    check(&[
        ("1.0.0-alpha.1", "1.0.0-alpha", Greater),
        ("1.0.0-alpha", "1.0.0-alpha.1", Less),
        ("1.0.0-alpha.1", "1.0.0-alpha.beta", Less),
        ("1.0.0-alpha.beta", "1.0.0-beta", Less),
        ("1.0.0-beta", "1.0.0-beta.2", Less),
        ("1.0.0-beta.2", "1.0.0-beta.11", Less),
        ("1.0.0-beta.11", "1.0.0-rc.1", Less),
        ("1.0.0-rc.1", "1.0.0", Less),
        ("1.0.0-alpha", "1", Less),
        ("1.0.0-beta.11", "1.0.0-beta.1", Greater),
        ("1.0.0-beta.10", "1.0.0-beta.9", Greater),
        ("1.0.0-beta.10", "1.0.0-beta.90", Less),
    ]);
}

// [ref: test/compare.ts::L94]
// [ref: test/compare.ts::L95]
// [ref: test/compare.ts::L96]
// [ref: test/compare.ts::L97]
// [ref: test/compare.ts::L98]
// [ref: test/compare.ts::L99]
// [ref: test/compare.ts::L100]
// [ref: test/compare.ts::L101]
// [ref: test/compare.ts::L102]
#[test]
fn compare_versions_build_metadata() {
    check(&[
        ("1.4.0-build.3928", "1.4.0-build.3928+sha.a8d9d4f", Equal),
        (
            "1.4.0-build.3928+sha.b8dbdb0",
            "1.4.0-build.3928+sha.a8d9d4f",
            Equal,
        ),
        ("1.0.0-alpha+001", "1.0.0-alpha", Equal),
        (
            "1.0.0-beta+exp.sha.5114f85",
            "1.0.0-beta+exp.sha.999999",
            Equal,
        ),
        ("1.0.0+20130313144700", "1.0.0", Equal),
        ("1.0.0+20130313144700", "2.0.0", Less),
        ("1.0.0+20130313144700", "1.0.1+11234343435", Less),
        ("1.0.1+1", "1.0.1+2", Equal),
        ("1.0.0+a-a", "1.0.0+a-b", Equal),
    ]);
}

// [ref: test/compare.ts::L108]
// [ref: test/compare.ts::L109]
// [ref: test/compare.ts::L110]
// [ref: test/compare.ts::L111]
#[test]
fn compare_versions_leading_v() {
    check(&[
        ("v1.0.0", "1.0.0", Equal),
        ("v1.0.0", "v1.0.0", Equal),
        ("v1.0.0", "v1.0.0", Equal),
        ("v1.0.0-alpha", "1.0.0-alpha", Equal),
    ]);
}

// [ref: test/compare.ts::L117]
// [ref: test/compare.ts::L118]
// [ref: test/compare.ts::L119]
// [ref: test/compare.ts::L120]
// [ref: test/compare.ts::L121]
// [ref: test/compare.ts::L122]
// [ref: test/compare.ts::L123]
#[test]
fn compare_versions_leading_zero() {
    check(&[
        ("01.0.0", "1", Equal),
        ("01.0.0", "1.0.0", Equal),
        ("1.01.0", "1.01.0", Equal),
        ("1.0.03", "1.0.3", Equal),
        ("1.0.03-alpha", "1.0.3-alpha", Equal),
        ("v01.0.0", "1.0.0", Equal),
        ("v01.0.0", "2.0.0", Less),
    ]);
}

// [ref: test/compare.ts::L129]
// [ref: test/compare.ts::L130]
// [ref: test/compare.ts::L131]
// [ref: test/compare.ts::L132]
// [ref: test/compare.ts::L133]
// [ref: test/compare.ts::L134]
// [ref: test/compare.ts::L135]
// [ref: test/compare.ts::L136]
// [ref: test/compare.ts::L137]
// [ref: test/compare.ts::L138]
// [ref: test/compare.ts::L139]
// [ref: test/compare.ts::L140]
// [ref: test/compare.ts::L141]
// [ref: test/compare.ts::L142]
// [ref: test/compare.ts::L143]
// [ref: test/compare.ts::L144]
// [ref: test/compare.ts::L145]
// [ref: test/compare.ts::L146]
// [ref: test/compare.ts::L147]
// [ref: test/compare.ts::L148]
// [ref: test/compare.ts::L149]
// [ref: test/compare.ts::L150]
#[test]
fn compare_versions_wildcards() {
    check(&[
        ("3", "3.x.x", Equal),
        ("3.3", "3.x.x", Equal),
        ("3.3.3", "3.x.x", Equal),
        ("3.x.x", "3.3.3", Equal),
        ("3.3.3", "3.X.X", Equal),
        ("3.3.3", "3.3.x", Equal),
        ("3.3.3", "3.*.*", Equal),
        ("3.3.3", "3.3.*", Equal),
        ("3.0.3", "3.0.*", Equal),
        ("0.7.x", "0.6.0", Greater),
        ("0.7.x", "0.6.0-asdf", Greater),
        ("0.7.x", "0.6.2", Greater),
        ("0.7.x", "0.7.0-asdf", Greater),
        ("1.2.*", "1.1.3", Greater),
        ("1.2.*", "1.1.9999", Greater),
        ("1.2.x", "1.0.0", Greater),
        ("1.2.x", "1.1.0", Greater),
        ("1.2.x", "1.1.3", Greater),
        ("2.*.*", "1.0.1", Greater),
        ("2.*.*", "1.1.3", Greater),
        ("2.x.x", "1.0.0", Greater),
        ("2.x.x", "1.1.3", Greater),
    ]);
}

// [ref: test/compare.ts::L175]
// [ref: test/compare.ts::L176]
// [ref: test/compare.ts::L177]
// [ref: test/compare.ts::L178]
// [ref: test/compare.ts::L179]
// [ref: test/compare.ts::L180]
// [ref: test/compare.ts::L181]
// [ref: test/compare.ts::L182]
// [ref: test/compare.ts::L183]
// [ref: test/compare.ts::L184]
// [ref: test/compare.ts::L185]
// [ref: test/compare.ts::L186]
// [ref: test/compare.ts::L187]
// [ref: test/compare.ts::L188]
// [ref: test/compare.ts::L189]
// [ref: test/compare.ts::L190]
// [ref: test/compare.ts::L191]
// [ref: test/compare.ts::L192]
// [ref: test/compare.ts::L193]
// [ref: test/compare.ts::L194]
// [ref: test/compare.ts::L195]
// [ref: test/compare.ts::L196]
// [ref: test/compare.ts::L197]
// [ref: test/compare.ts::L198]
// [ref: test/compare.ts::L199]
// [ref: test/compare.ts::L200]
// [ref: test/compare.ts::L201]
// [ref: test/compare.ts::L202]
// [ref: test/compare.ts::L203]
// [ref: test/compare.ts::L204]
#[test]
fn compare_versions_misc() {
    check(&[
        ("0.1.20", "0.1.5", Greater),
        ("0.6.1-1", "0.6.1-0", Greater),
        ("1", "0.0.0-beta", Greater),
        ("1", "0.2.3", Greater),
        ("1", "0.2.4", Greater),
        ("1", "1.0.0-0", Greater),
        ("1", "1.0.0-beta", Greater),
        ("1.0", "0.0.0", Greater),
        ("1.0", "0.1.0", Greater),
        ("1.0", "0.1.2", Greater),
        ("1.0.0", "0.0.0", Greater),
        ("1.0.0", "0.0.1", Greater),
        ("1.0.0", "0.2.3", Greater),
        ("1.0.0-beta.2", "1.0.0-beta.1", Greater),
        ("1.2.2", "1.2.1", Greater),
        ("2", "1.0.0", Greater),
        ("2", "1.0.0-beta", Greater),
        ("2", "1.9999.9999", Greater),
        ("2.0.0", "1.0.0", Greater),
        ("2.0.0", "1.1.1", Greater),
        ("2.0.0", "1.2.9", Greater),
        ("2.0.0", "1.9999.9999", Greater),
        ("2.3", "2.2.1", Greater),
        ("2.3", "2.2.2", Greater),
        ("2.4", "2.3.0", Greater),
        ("2.4", "2.3.5", Greater),
        ("3.2.1", "2.3.2", Greater),
        ("3.2.1", "3.2.0", Greater),
        ("v0.5.4-pre", "0.5.4-alpha", Greater),
        ("v3.2.1", "v2.3.2", Greater),
    ]);
}

// [ref: test/compare.ts::L161]
// [ref: test/compare.ts::L162]
// [ref: test/compare.ts::L163]
// [ref: test/compare.ts::L276]
// [ref: test/compare.ts::L277]
// [ref: test/compare.ts::L278]
#[test]
fn invalid_versions_error_in_both_functions() {
    for v in ["6.3.", "1.2.3a", "1.2.-3a"] {
        let expected = Err(Error::InvalidVersion(v.to_owned()));
        assert_eq!(compare_versions(v, v), expected);
        assert_eq!(compare(v, v, ">"), expected.map(|_: Ordering| true));
    }
}

// [ref: test/compare.ts::L264]
// [ref: test/compare.ts::L265]
// [ref: test/compare.ts::L266]
#[test]
fn compare_rejects_unknown_operators() {
    for op in ["", "foo", "> "] {
        assert_eq!(
            compare("3.2.1", "3.2.0", op),
            Err(Error::InvalidOperator),
            "{op:?}"
        );
    }
}

// [ref: test/compare.ts::L288]
// [ref: test/compare.ts::L289]
// [ref: test/compare.ts::L290]
// [ref: test/compare.ts::L291]
// [ref: test/compare.ts::L292]
// [ref: test/compare.ts::L293]
// [ref: test/compare.ts::L294]
// [ref: test/compare.ts::L295]
// [ref: test/compare.ts::L296]
// [ref: test/compare.ts::L297]
// [ref: test/compare.ts::L298]
// [ref: test/compare.ts::L299]
// [ref: test/compare.ts::L300]
// [ref: test/compare.ts::L301]
// [ref: test/compare.ts::L302]
// [ref: test/compare.ts::L303]
#[test]
fn compare_applies_operators() {
    for (v1, v2, op, expected) in [
        ("10.1.8", "10.0.4", ">", true),
        ("10.1.8", "10.0.4", ">=", true),
        ("10.0.1", "10.0.1", "=", true),
        ("10.0.1", "10.1.*", "=", false),
        ("3.3.3", "3.x.x", "<", false),
        ("3.3.3", "3.x.x", ">=", true),
        ("10.1.1", "10.2.2", "<", true),
        ("10.1.1", "10.0.2", "<", false),
        ("10.1.1", "10.2.2", "<=", true),
        ("10.1.1", "10.1.1", "<=", true),
        ("10.1.1", "10.0.2", "<=", false),
        ("10.1.1", "10.0.2", ">=", true),
        ("10.1.1", "10.1.1", ">=", true),
        ("10.1.1", "10.2.2", ">=", false),
        ("10.1.1", "10.2.2", "!=", true),
        ("10.1.1", "10.1.1", "!=", false),
    ] {
        assert_eq!(compare(v1, v2, op), Ok(expected), "{v1} {op} {v2}");
    }
}

// [ref: test/compare.ts::L269]
#[test]
fn compare_throws_the_errors_of_compare_versions() {
    for v in ["6.3.", "1.2.3a", "1.2.-3a"] {
        assert_eq!(
            compare(v, v, ">"),
            Err(Error::InvalidVersion(v.to_owned())),
            "{v}"
        );
    }
}
