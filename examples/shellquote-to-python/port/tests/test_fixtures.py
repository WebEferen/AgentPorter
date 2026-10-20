import importlib.util
from pathlib import Path
from typing import Any

import pytest
from oracle_fixtures import case_id, load_cases

from shellquote import ShellQuoteError

BINDINGS_PATH = Path(__file__).resolve().parent.parent / "porter" / "bindings.py"


def _load_bindings() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("porter_bindings", BINDINGS_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bindings: dict[str, Any] = module.BINDINGS
    return bindings


BINDINGS = _load_bindings()


@pytest.mark.parametrize("case", load_cases(), ids=case_id)
def test_oracle_case(case: dict[str, Any]) -> None:
    binding = BINDINGS[case["call"]]
    inp = case["input"]
    args, kwargs = inp.get("args", []), inp.get("kwargs", {})
    expect = case["expect"]
    if expect["kind"] == "value":
        assert binding(args, kwargs, inp) == expect["value"]
        return
    with pytest.raises(ShellQuoteError) as excinfo:
        binding(args, kwargs, inp)
    assert type(excinfo.value).__name__ == expect["category"]
    assert str(excinfo.value) == expect["message"]
