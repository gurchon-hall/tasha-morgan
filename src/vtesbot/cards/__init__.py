"""Card effect modules + implementation registry (CLAUDE.md §5/§6).
Importing loads every card module in sorted name order, which fixes the
provider registration order; most of the 2P pool has no module yet."""

import importlib
import pkgutil

__all__: list[str] = []  # import-for-side-effect only; nothing is re-exported.

_NOT_CARDS = frozenset({"registry", "card", "common"})

for _info in sorted(pkgutil.iter_modules(__path__), key=lambda info: info.name):
    if _info.name.startswith("_") or _info.name in _NOT_CARDS:
        continue
    importlib.import_module(f"{__name__}.{_info.name}")
