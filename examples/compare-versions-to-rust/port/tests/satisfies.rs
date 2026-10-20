use compare_versions_port::satisfies;

fn check(rows: &[(&str, &str, bool)]) {
    for &(v, range, expected) in rows {
        assert_eq!(satisfies(v, range), Ok(expected), "{v} {range}");
    }
}

// [ref: test/satisfies.ts::L15]
// [ref: test/satisfies.ts::L16]
// [ref: test/satisfies.ts::L17]
// [ref: test/satisfies.ts::L18]
// [ref: test/satisfies.ts::L19]
// [ref: test/satisfies.ts::L20]
// [ref: test/satisfies.ts::L21]
// [ref: test/satisfies.ts::L22]
// [ref: test/satisfies.ts::L23]
// [ref: test/satisfies.ts::L24]
// [ref: test/satisfies.ts::L25]
// [ref: test/satisfies.ts::L26]
// [ref: test/satisfies.ts::L27]
// [ref: test/satisfies.ts::L28]
// [ref: test/satisfies.ts::L29]
#[test]
fn satisfies_tilde() {
    check(&[
        ("1.0.0", "~1.0.1", false),
        ("1.0.1", "~1.0.1", true),
        ("1.2.5", "~1.2.3", true),
        ("1.3.0", "~1.2.3", false),
        ("1.2.5", "~1.2", true),
        ("1.3.0", "~1.2", false),
        ("1.0.0", "~1", true),
        ("2.0.0", "~1", false),
        ("0.2.5", "~0.2.3", true),
        ("0.3.0", "~0.2.3", false),
        ("0.2.5", "~0.2", true),
        ("0.3.0", "~0.2", false),
        ("0.0.0", "~0", true),
        ("0.1.2", "~0", true),
        ("1.0.0", "~0", false),
    ]);
}

// [ref: test/satisfies.ts::L35]
// [ref: test/satisfies.ts::L36]
// [ref: test/satisfies.ts::L37]
// [ref: test/satisfies.ts::L38]
// [ref: test/satisfies.ts::L39]
// [ref: test/satisfies.ts::L40]
// [ref: test/satisfies.ts::L41]
// [ref: test/satisfies.ts::L42]
// [ref: test/satisfies.ts::L43]
// [ref: test/satisfies.ts::L44]
// [ref: test/satisfies.ts::L45]
// [ref: test/satisfies.ts::L46]
#[test]
fn satisfies_caret() {
    check(&[
        ("1.0.0", "^1", true),
        ("1.0.0", "^1.0", true),
        ("1.0.0", "^1.0.0", true),
        ("1.2.0", "^1.0.0", true),
        ("v1.2.0", "^1.0.0", true),
        ("2.0.0", "^1.0.0", false),
        ("1.0.0", "^1.2.0", false),
        ("1.0.1", "^1.2.0", false),
        ("1.3.4", "^1.2.3", true),
        ("2.0.0", "^1.2.3", false),
        ("0.3.0", "^0.2.3", false),
        ("0.0.4", "^0.0.3", false),
    ]);
}

// [ref: test/satisfies.ts::L51]
// [ref: test/satisfies.ts::L52]
// [ref: test/satisfies.ts::L53]
// [ref: test/satisfies.ts::L54]
// [ref: test/satisfies.ts::L55]
// [ref: test/satisfies.ts::L56]
// [ref: test/satisfies.ts::L57]
// [ref: test/satisfies.ts::L58]
// [ref: test/satisfies.ts::L59]
// [ref: test/satisfies.ts::L60]
// [ref: test/satisfies.ts::L61]
// [ref: test/satisfies.ts::L62]
// [ref: test/satisfies.ts::L63]
// [ref: test/satisfies.ts::L64]
// [ref: test/satisfies.ts::L65]
// [ref: test/satisfies.ts::L66]
// [ref: test/satisfies.ts::L67]
// [ref: test/satisfies.ts::L68]
// [ref: test/satisfies.ts::L69]
// [ref: test/satisfies.ts::L70]
// [ref: test/satisfies.ts::L71]
// [ref: test/satisfies.ts::L72]
// [ref: test/satisfies.ts::L73]
// [ref: test/satisfies.ts::L74]
// [ref: test/satisfies.ts::L75]
// [ref: test/satisfies.ts::L76]
// [ref: test/satisfies.ts::L77]
// [ref: test/satisfies.ts::L78]
// [ref: test/satisfies.ts::L79]
// [ref: test/satisfies.ts::L80]
// [ref: test/satisfies.ts::L81]
// [ref: test/satisfies.ts::L82]
// [ref: test/satisfies.ts::L83]
#[test]
fn satisfies_comparators() {
    check(&[
        ("1.2.0", ">1.0.0", true),
        ("1.2.0", "<1.0.0", false),
        ("1.0.0", "<=1.0.0", true),
        ("1.0.0", "<=2.0.0", true),
        ("1.0.1", "1.0.0", false),
        ("1.0.0", "1.0.0", true),
        ("10.1.8", ">10.0.4", true),
        ("10.1.8", ">=10.0.4", true),
        ("10.0.1", "=10.0.1", true),
        ("10.0.1", "=10.1.*", false),
        ("10.1.1", "<10.2.2", true),
        ("10.1.1", "<10.0.2", false),
        ("10.1.1", "<=10.2.2", true),
        ("10.1.1", "<=10.1.1", true),
        ("10.1.1", "<=10.0.2", false),
        ("10.1.1", ">=10.0.2", true),
        ("10.1.1", ">=10.1.1", true),
        ("10.1.1", ">=10.2.2", false),
        ("11.0.0", ">=10.1.1", true),
        ("3", "3.x.x", true),
        ("3.3", "3.x.x", true),
        ("3.3.3", "3.x.x", true),
        ("3.x.x", "3.3.3", true),
        ("3.3.3", "3.X.X", true),
        ("3.3.3", "3.3.x", true),
        ("3.3.3", "3.*.*", true),
        ("3.3.3", "3.3.*", true),
        ("3.0.3", "3.0.*", true),
        ("1.1.0", "1.2.x", false),
        ("1.1.0", "2.x.x", false),
        ("2.0.0", "<2.x.x", false),
        ("2.0.0", "<=2.x.x", true),
        ("2.0.0", ">2.x.x", false),
    ]);
}

// [ref: test/satisfies.ts::L88]
// [ref: test/satisfies.ts::L89]
// [ref: test/satisfies.ts::L90]
// [ref: test/satisfies.ts::L91]
// [ref: test/satisfies.ts::L92]
// [ref: test/satisfies.ts::L93]
// [ref: test/satisfies.ts::L94]
// [ref: test/satisfies.ts::L95]
// [ref: test/satisfies.ts::L96]
#[test]
fn satisfies_pre_release() {
    check(&[
        ("1.2.3-beta.4", "~1.2.3-beta.2", true),
        ("1.2.3-beta.1", "~1.2.3-beta.2", false),
        ("1.2.4-beta.2", "~1.2.3-beta.2", false),
        ("1.2.3-beta.4", "^1.2.3-beta.2", true),
        ("1.2.4-beta.2", "^1.2.3-beta.2", false),
        ("2.0.0", "^1.2.3-beta.2", false),
        ("0.0.3-beta.2", "^0.0.3-beta", true),
        ("0.0.3-pr.2", "^0.0.3-beta", true),
        ("0.0.4", "^0.0.3-beta", false),
    ]);
}

// [ref: test/satisfies.ts::L102]
// [ref: test/satisfies.ts::L103]
// [ref: test/satisfies.ts::L104]
// [ref: test/satisfies.ts::L105]
// [ref: test/satisfies.ts::L106]
// [ref: test/satisfies.ts::L107]
// [ref: test/satisfies.ts::L108]
// [ref: test/satisfies.ts::L109]
// [ref: test/satisfies.ts::L110]
// [ref: test/satisfies.ts::L111]
// [ref: test/satisfies.ts::L112]
// [ref: test/satisfies.ts::L113]
// [ref: test/satisfies.ts::L114]
// [ref: test/satisfies.ts::L115]
// [ref: test/satisfies.ts::L116]
// [ref: test/satisfies.ts::L117]
// [ref: test/satisfies.ts::L118]
// [ref: test/satisfies.ts::L119]
// [ref: test/satisfies.ts::L120]
// [ref: test/satisfies.ts::L121]
// [ref: test/satisfies.ts::L122]
// [ref: test/satisfies.ts::L123]
#[test]
fn satisfies_comparator_sets() {
    check(&[
        ("1.1.0", ">=1.2.7 <1.3.0", false),
        ("1.2.9", ">=1.2.7 <1.3.0", true),
        ("1.3.0", ">=1.2.7 <1.3.0", false),
        ("1.2.9", "   >=1.2.7     <1.3.0 ", true),
        ("1.3.0", "   >=1.2.7     <1.3.0 ", false),
        ("1.2.7", "1.2.7 || >=1.2.9 <2.0.0", true),
        ("1.2.9", "1.2.7 || >=1.2.9 <2.0.0", true),
        ("1.4.6", "1.2.7 || >=1.2.9 <2.0.0", true),
        ("1.2.8", "1.2.7 || >=1.2.9 <2.0.0", false),
        ("2.0.0", "1.2.7 || >=1.2.9 <2.0.0", false),
        ("2.0.0", "1.2.7 || >=1.2.9 <2.0.0", false),
        ("1.4.6", "  1.2.7  || >=1.2.9    <2.0.0   ", true),
        ("2.0.0", "  1.2.7  || >=1.2.9    <2.0.0   ", false),
        ("1.0.0", "1.2.3 - 2.3.4", false),
        ("1.2.3", "1.2.3 - 2.3.4", true),
        ("1.5.1", "1.2.3 - 2.3.4", true),
        ("2.3.4", "1.2.3 - 2.3.4", true),
        ("2.4.0", "1.2.3 - 2.3.4", false),
        ("12.25.0", "^12.22.0 || ^14.17.0 || >=16.0.0", true),
        ("14.25.0", "^12.22.0 || ^14.17.0 || >=16.0.0", true),
        ("17", "^12.22.0 || ^14.17.0 || >=16.0.0", true),
        ("15", "^12.22.0 || ^14.17.0 || >=16.0.0", false),
    ]);
}

// [ref: test/satisfies.ts::L129]
// [ref: test/satisfies.ts::L130]
// [ref: test/satisfies.ts::L131]
// [ref: test/satisfies.ts::L132]
// [ref: test/satisfies.ts::L133]
// [ref: test/satisfies.ts::L134]
// [ref: test/satisfies.ts::L135]
#[test]
fn satisfies_malformed() {
    check(&[
        ("1.2.3", "> 1.2.3", false),
        ("1.2.4", "> 1.2.3", true),
        ("1.2.3", "> 1.2.3 < 1.2.5", false),
        ("1.2.4", "> 1.2.3 < 1.2.5", true),
        ("0.0.0", "> 1.2.3 <=  1.2.5   ||   0.0.0", true),
        ("1.2.5", "> 1.2.3 <=  1.2.5   ||   0.0.0", true),
        ("1.3.0", "> 1.2.3 <=  1.2.5   ||   0.0.0", false),
    ]);
}
