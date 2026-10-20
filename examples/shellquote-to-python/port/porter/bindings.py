"""Parity harness bindings: Go call ids to the shellquote API."""

from collections.abc import Callable
from typing import Any

from shellquote import join, split

BINDINGS: dict[str, Callable[[list[Any], dict[str, Any], dict[str, Any]], object]] = {
    "github.com/kballard/go-shellquote:Join": lambda args, _kw, _in: join(*args),
    "github.com/kballard/go-shellquote:Split": lambda args, _kw, _in: split(args[0]),
}
