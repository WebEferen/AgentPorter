"""Run the ported reference tests and write JUnit XML for `porter parity reftests junit`.

Rust test names cannot hold `[ref: ...]`, so each ported test carries a `/// [ref: <id>]` doc line above its
`fn`. This runs `cargo test --lib --test reference` from the crate root, maps each test to its ref through
those doc lines and writes one testcase per test, named `<test> [ref: <id>]`.

    python3 -I .porter/tools/cargo_junit.py <out.xml>

Exit code: cargo's, or 2 when no test results were read or a tagged test did not run.
"""

import re
import subprocess
import sys
import xml.etree.ElementTree as ET

SOURCES = ("src/lib.rs", "tests/reference.rs")
REF_LINE = re.compile(r"^\s*///\s*(\[ref:[^\]]+\])\s*$")
FN_LINE = re.compile(r"^\s*(?:pub\s+)?fn\s+(\w+)")
RESULT_LINE = re.compile(r"^test (\S+) \.\.\. (ok|FAILED|ignored)\b")


def refs_by_fn() -> dict[str, str]:
    refs: dict[str, str] = {}
    for path in SOURCES:
        pending = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                if m := REF_LINE.match(line):
                    pending = m.group(1)
                elif pending and (m := FN_LINE.match(line)):
                    if m.group(1) in refs:
                        sys.exit(f"cargo_junit: test fn {m.group(1)} is defined twice")
                    refs[m.group(1)] = pending
                    pending = None
    return refs


def main() -> int:
    out_path = sys.argv[1]
    refs = refs_by_fn()
    proc = subprocess.run(["cargo", "test", "--lib", "--test", "reference", "--color", "never"],
                          capture_output=True, text=True)
    results = [m.groups() for m in map(RESULT_LINE.match, proc.stdout.splitlines()) if m]
    if not results:
        sys.stderr.write(proc.stdout + proc.stderr)
        print("cargo_junit: no test results in cargo's output", file=sys.stderr)
        return 2
    suite = ET.Element("testsuite", name="humps", tests=str(len(results)))
    ran = set()
    for name, status in results:
        fn = name.rsplit("::", 1)[-1]
        ran.add(fn)
        case = ET.SubElement(suite, "testcase", classname="cargo", name=f"{name} {refs[fn]}" if fn in refs else name)
        if status == "FAILED":
            ET.SubElement(case, "failure", message="test failed")
        elif status == "ignored":
            ET.SubElement(case, "skipped")
    missing = sorted(set(refs) - ran)
    for fn in missing:
        case = ET.SubElement(suite, "testcase", classname="cargo", name=f"{fn} {refs[fn]}")
        ET.SubElement(case, "error", message="tagged test did not run")
    ET.ElementTree(suite).write(out_path, encoding="utf-8", xml_declaration=True)
    print(f"cargo_junit: {len(results)} tests, {len(refs)} tagged, {len(missing)} tagged but not run -> {out_path}")
    return 2 if missing else proc.returncode


if __name__ == "__main__":
    sys.exit(main())
