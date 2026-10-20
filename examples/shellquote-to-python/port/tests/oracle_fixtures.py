"""Cases recorded from go-shellquote, read from .porter/fixtures."""

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent.parent / ".porter" / "fixtures" / "root"
SPLIT_CALL = "github.com/kballard/go-shellquote:Split"


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        cases.extend(json.loads(path.read_text(encoding="utf-8"))["cases"])
    if not cases:
        raise FileNotFoundError(f"no fixture cases under {FIXTURES_DIR}")
    return cases


def case_id(case: dict[str, Any]) -> str:
    return str(case["case"])
