"""Copy to bindings.py next to harness.py. One entry per source call id in .porter/fixtures; nothing else.

Each binding is f(args, kwargs, input) with tagged values already decoded ($bytes is bytes, $set is a set,
$float nan is math.nan). Bindings translate calling conventions only: never convert or patch a return value."""
from harness import UNDEFINED

from mylib import ms, slugify, Slugger, DEFAULT_SEPARATOR

BINDINGS = {
    # A JavaScript options object becomes keyword arguments.
    "ms:default": lambda args, kwargs, input: ms(args[0], long=(args[1] if len(args) > 1 else {}).get("long", False)),

    # Positional and keyword arguments map straight through.
    "slugify.slugify:slugify": lambda args, kwargs, input: slugify(*args, **kwargs),

    # <Class>.<method>: build the receiver from input["init"], then call the method.
    "pkg.mod:Slugger.slug": lambda args, kwargs, input: Slugger(*input["init"].get("args", [])).slug(*args),

    # Constant reads (input is {}): return the port's constant.
    "slugify.slugify:DEFAULT_SEPARATOR": lambda args, kwargs, input: DEFAULT_SEPARATOR,
}

# Where the source returned JavaScript undefined and the port returns None, the binding returns UNDEFINED.
