"""Run `cargo test` and write a JUnit report that `porter parity reftests junit` can import.

Rust test names cannot hold `[ref: <id>]`, so the tags live in the `///` or `//` comment lines directly
above `#[test] fn <name>`. Each tag becomes its own <testcase> named `<test path> [ref: <id>]`.

Usage: python3 .porter/tools/cargo_junit.py <crate root> <output.xml> [extra cargo test args...]
"""
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

REF = re.compile(r"\[ref:\s*([^\]]+?)\s*\]")
RESULT = re.compile(r"^test (\S+) \.\.\. (ok|FAILED|ignored)\b")


def refs_by_fn(root: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(list(root.glob("src/**/*.rs")) + list(root.glob("tests/**/*.rs"))):
        pending: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("//"):
                pending += REF.findall(s)
                continue
            if s.startswith("#["):
                continue
            m = re.match(r"(?:pub(?:\([^)]*\))?\s+)?fn\s+(\w+)", s)
            if m and pending:
                found.setdefault(m.group(1), []).extend(pending)
            pending = []
    return found


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0 if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help") else 2
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    proc = subprocess.run(["cargo", "test", "--no-fail-fast", *sys.argv[3:]], cwd=root,
                          capture_output=True, text=True)
    tags = refs_by_fn(root)
    cases = []
    for line in proc.stdout.splitlines():
        m = RESULT.match(line)
        if not m:
            continue
        path, status = m.groups()
        refs = tags.get(path.split("::")[-1], [])
        for name in [f"{path} [ref: {r}]" for r in dict.fromkeys(refs)] or [path]:
            body = {"ok": "", "FAILED": "<failure/>", "ignored": "<skipped/>"}[status]
            cases.append(f'  <testcase classname="cargo" name={quoteattr(name)}>{body}</testcase>')
    out.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="cargo test">\n'
                   + "\n".join(cases) + "\n</testsuite>\n", encoding="utf-8")
    print(f"{len(cases)} testcases written to {out}; cargo test exit {proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
