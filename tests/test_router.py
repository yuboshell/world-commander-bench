"""RouterClient: route micro→small, macro→large (the hierarchy the macro curve motivates)."""
from arena.commands import Command
from arena.model_client import RouterClient


class _Stub:
    def __init__(self, tag):
        self.tag = tag
        self.calls = 0

    def act(self, world, command):
        self.calls += 1
        return {("_", self.tag)}


def _cmd(gran):
    return Command(text="x", acceptable={"red": {"N"}}, granularity=gran)


def test_router_macro_to_large_micro_to_small():
    s, l = _Stub("small"), _Stub("large")
    r = RouterClient(s, l)
    assert r.act(None, _cmd("micro")) == {("_", "small")}
    assert r.act(None, _cmd("macro")) == {("_", "large")}
    assert (s.calls, l.calls) == (1, 1)


def test_router_custom_policy():
    s, l = _Stub("small"), _Stub("large")
    r = RouterClient(s, l, route=lambda c: "large")
    r.act(None, _cmd("micro"))
    r.act(None, _cmd("macro"))
    assert (s.calls, l.calls) == (0, 2)
