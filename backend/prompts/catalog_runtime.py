"""Authorized, request-local catalog resolution with immutable audit snapshots."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

from .catalog_defaults import builtin_entries

_scope = ContextVar("prompt_catalog_scope", default=None)


@contextmanager
def prompt_scope(user_id):
    token = _scope.set({"user_id": user_id, "entries": None, "used": {}})
    try:
        yield
    finally:
        _scope.reset(token)


def scoped():
    return _scope.get() is not None


def _entries():
    state = _scope.get()
    if state is None:
        return [{**entry, "revision": 1} for entry in builtin_entries()]
    if state["entries"] is None:
        from .catalog import actor, serialize, usable
        from .models import PromptEntry
        user = actor(state["user_id"])
        stored = list(PromptEntry.objects.select_related("owner"))
        existing_ids = {entry.pk for entry in stored}
        # Read-only previews must not seed rows. Persisted disabled/private rows
        # still shadow their builtin defaults and can never fall back.
        state["entries"] = [serialize(entry, user) for entry in stored if usable(user, entry)]
        state["entries"] += [{**entry, "revision": 1} for entry in builtin_entries()
                             if entry["id"] not in existing_ids]
    return state["entries"]


def _remember(entry):
    state = _scope.get()
    if state is not None:
        state["used"][entry["id"]] = deepcopy(entry)
    return deepcopy(entry)


def options(module, category):
    return [deepcopy(entry) for entry in _entries()
            if entry["module"] == module and entry["category"] == category]


def resolve_layout_entry(entries, value):
    entry = next((entry for entry in entries if entry["id"] == value), None)
    if entry is None:
        entry = next((entry for entry in entries if entry.get("builtin")
                      and entry.get("legacy_value") and entry["legacy_value"] == value), None)
    if entry is not None:
        return entry
    named = [entry for entry in entries if entry.get("name") == value]
    if len(named) > 1:
        raise ValueError("单页布局名称不唯一，请按编号重新选择。")
    if not named:
        raise ValueError("单页布局不存在、已停用或无权使用，请重新选择。")
    return named[0]


def option(module, category, value):
    entries = [entry for entry in _entries()
               if entry["module"] == module and entry["category"] == category]
    if module == "image" and category == "layout":
        return _remember(resolve_layout_entry(entries, value))
    entry = next((entry for entry in entries if entry["id"] == value), None)
    if entry is None:
        entry = next((entry for entry in entries if entry.get("builtin")
                      and entry.get("legacy_value") and entry["legacy_value"] == value), None)
    if entry is None:
        raise ValueError("提示词选项不存在、已停用或无权使用，请重新选择。")
    return _remember(entry)


def base(module):
    return option(module, "base", f"{module}.base.default")["content"]


def snapshot():
    state = _scope.get()
    return deepcopy(list(state["used"].values())) if state else []
