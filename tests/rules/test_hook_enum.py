"""`engine/hooks.py::Hook` is the single list of hook names: every engine
`*_HOOK` constant is one of its members, and every member outside
`UNWIRED_HOOKS` has an engine constant (hence a dispatch site)."""

import importlib
import pkgutil

import vtesbot.engine
from vtesbot.cards import registry
from vtesbot.engine.hooks import UNWIRED_HOOKS, Hook


def _engine_hook_constants() -> dict[str, object]:
    found: dict[str, object] = {}
    for info in pkgutil.walk_packages(vtesbot.engine.__path__, "vtesbot.engine."):
        module = importlib.import_module(info.name)
        for name, value in vars(module).items():
            if name.endswith("_HOOK"):
                found[f"{info.name}.{name}"] = value
    return found


def test_every_engine_hook_constant_is_a_hook_member():
    not_members = {k: v for k, v in _engine_hook_constants().items() if not isinstance(v, Hook)}
    assert not_members == {}


def test_every_wired_member_has_an_engine_constant():
    wired = set(_engine_hook_constants().values())
    assert set(Hook) - UNWIRED_HOOKS == wired


def test_registry_reexports_the_engine_enum():
    assert registry.Hook is Hook
