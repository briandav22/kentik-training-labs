"""Kentik training labs: a made-up network that sends flow to a Universal Agent."""
import sys

__version__ = "0.1.0"

# Python 3.4 (Ubuntu 14.04) has no typing module. The hints are only hints, so
# stand in a do-nothing one rather than make students install anything.
try:
    import typing  # noqa: F401
except ImportError:
    import types

    class _Hint(object):
        def __getitem__(self, item):
            return self

    _typing = types.ModuleType("typing")
    for _name in ("Any", "Callable", "Dict", "List", "Optional", "Tuple"):
        setattr(_typing, _name, _Hint())
    sys.modules["typing"] = _typing
