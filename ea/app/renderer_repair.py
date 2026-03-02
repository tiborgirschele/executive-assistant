from __future__ import annotations

import copy
import functools
import inspect
import os
import re
import time
from typing import Any

INVALID_TEMPLATE_RE = re.compile(r"(?i)(invalid template id|source/data/id:\s*invalid template id|template[_ /-]?id)")
RENDERER_UNAVAILABLE_RE = re.compile(r"(?i)(markupgo|renderer).*(http\s*[45]\d\d|timeout|temporar|unavailable|validation)")
JSONISH_RE = re.compile(r"(?s)^\s*[\[{].*[\]}]\s*$")

_BREAKER_UNTIL = 0.0
_PATCHED_MODULE_IDS: set[int] = set()


def _now() -> float:
    return time.time()


def _mask(value: str) -> str:
    v = (value or "").strip()
    if len(v) <= 8:
        return v or "none"
    return f"{v[:4]}...{v[-4:]}"


def breaker_open() -> bool:
    return _now() < _BREAKER_UNTIL


def open_breaker(reason: str) -> None:
    global _BREAKER_UNTIL
    ttl = max(60, int(os.getenv("EA_RENDERER_BREAKER_TTL_SEC", "21600")))
    _BREAKER_UNTIL = _now() + ttl
    print(f"[EA RENDER REPAIR] recipe=breaker_open_optional_skill reason={reason} ttl_sec={ttl}")


def classify_renderer_failure(exc_or_text: Any) -> str:
    text = "" if exc_or_text is None else str(exc_or_text)
    if INVALID_TEMPLATE_RE.search(text):
        return "invalid_template_id"
    if RENDERER_UNAVAILABLE_RE.search(text):
        return "renderer_unavailable"
    return "unknown"


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        val = (item or "").strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def discover_known_good_template_ids() -> list[str]:
    keys = [
        "EA_MARKUPGO_TEMPLATE_ID_SAFE",
        "EA_MARKUPGO_TEMPLATE_ID_KNOWN_GOOD",
        "EA_MARKUPGO_TEMPLATE_ID_FALLBACK",
        "MARKUPGO_TEMPLATE_ID_SAFE",
        "MARKUPGO_TEMPLATE_ID_KNOWN_GOOD",
        "MARKUPGO_TEMPLATE_ID_FALLBACK",
    ]
    return _unique([os.getenv(k, "") for k in keys])


def _collect_strings(value: Any, out: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        out.append(value)
        return
    if isinstance(value, dict):
        for inner in value.values():
            _collect_strings(inner, out)
        return
    if isinstance(value, (list, tuple, set)):
        for inner in value:
            _collect_strings(inner, out)
        return


def extract_text_fallback(*values: Any) -> str | None:
    candidates: list[str] = []
    for value in values:
        _collect_strings(value, candidates)

    scored: list[tuple[tuple[int, int], str]] = []
    for raw in candidates:
        text = raw.strip()
        if len(text) < 40:
            continue
        if JSONISH_RE.match(text):
            continue
        if INVALID_TEMPLATE_RE.search(text):
            continue
        if "Traceback (most recent call last):" in text:
            continue
        alpha = sum(ch.isalpha() for ch in text)
        spaces = text.count(" ")
        if alpha < 20 or spaces < 4:
            continue
        scored.append(((alpha, len(text)), text))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def rewrite_template_ids(value: Any, new_id: str) -> tuple[Any, bool]:
    clone = copy.deepcopy(value)
    changed = False

    def walk(node: Any) -> None:
        nonlocal changed
        if isinstance(node, dict):
            for key in list(node.keys()):
                lowered = str(key).lower()
                current = node[key]
                if lowered in {"template_id", "templateid", "source_id", "source_data_id"} and isinstance(current, str):
                    if current != new_id:
                        node[key] = new_id
                        changed = True
                        current = node[key]
                if lowered == "source" and isinstance(current, dict):
                    data = current.get("data")
                    if isinstance(data, dict) and isinstance(data.get("id"), str) and data.get("id") != new_id:
                        data["id"] = new_id
                        changed = True
                walk(current)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, tuple):
            for item in node:
                walk(item)

    walk(clone)
    return clone, changed


def _patch_template_ids_in_call(args: tuple[Any, ...], kwargs: dict[str, Any], template_id: str) -> tuple[tuple[Any, ...], dict[str, Any], bool]:
    changed = False
    new_args = list(args)
    new_kwargs = dict(kwargs)

    for idx, value in enumerate(new_args):
        if isinstance(value, (dict, list, tuple)):
            rewritten, did_change = rewrite_template_ids(value, template_id)
            if did_change:
                new_args[idx] = rewritten
                changed = True

    for key, value in list(new_kwargs.items()):
        if isinstance(value, (dict, list, tuple)):
            rewritten, did_change = rewrite_template_ids(value, template_id)
            if did_change:
                new_kwargs[key] = rewritten
                changed = True

    return tuple(new_args), new_kwargs, changed


def _wrap_renderer_callable(name: str, fn):
    if getattr(fn, "_ea_renderer_wrapped", False):
        return fn

    async def _async_logic(*args, **kwargs):
        if breaker_open():
            fallback = extract_text_fallback(args, kwargs)
            if fallback:
                print(f"[EA RENDER REPAIR] recipe=renderer_text_only callable={name} breaker=open")
                return fallback

        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            fault = classify_renderer_failure(exc)
            if fault == "invalid_template_id":
                for template_id in discover_known_good_template_ids():
                    patched_args, patched_kwargs, changed = _patch_template_ids_in_call(args, kwargs, template_id)
                    if not changed:
                        continue
                    try:
                        result = await fn(*patched_args, **patched_kwargs)
                        print(f"[EA RENDER REPAIR] recipe=renderer_template_swap callable={name} template={_mask(template_id)}")
                        return result
                    except Exception as retry_exc:
                        print(f"[EA RENDER REPAIR] retry_failed recipe=renderer_template_swap callable={name} template={_mask(template_id)} fault={classify_renderer_failure(retry_exc)}")
                fallback = extract_text_fallback(args, kwargs)
                if fallback:
                    open_breaker(fault)
                    print(f"[EA RENDER REPAIR] recipe=renderer_text_only callable={name} reason={fault}")
                    return fallback
            elif fault == "renderer_unavailable":
                fallback = extract_text_fallback(args, kwargs)
                if fallback:
                    print(f"[EA RENDER REPAIR] recipe=renderer_text_only callable={name} reason={fault}")
                    return fallback
            raise

    def _sync_logic(*args, **kwargs):
        if breaker_open():
            fallback = extract_text_fallback(args, kwargs)
            if fallback:
                print(f"[EA RENDER REPAIR] recipe=renderer_text_only callable={name} breaker=open")
                return fallback

        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            fault = classify_renderer_failure(exc)
            if fault == "invalid_template_id":
                for template_id in discover_known_good_template_ids():
                    patched_args, patched_kwargs, changed = _patch_template_ids_in_call(args, kwargs, template_id)
                    if not changed:
                        continue
                    try:
                        result = fn(*patched_args, **patched_kwargs)
                        print(f"[EA RENDER REPAIR] recipe=renderer_template_swap callable={name} template={_mask(template_id)}")
                        return result
                    except Exception as retry_exc:
                        print(f"[EA RENDER REPAIR] retry_failed recipe=renderer_template_swap callable={name} template={_mask(template_id)} fault={classify_renderer_failure(retry_exc)}")
                fallback = extract_text_fallback(args, kwargs)
                if fallback:
                    open_breaker(fault)
                    print(f"[EA RENDER REPAIR] recipe=renderer_text_only callable={name} reason={fault}")
                    return fallback
            elif fault == "renderer_unavailable":
                fallback = extract_text_fallback(args, kwargs)
                if fallback:
                    print(f"[EA RENDER REPAIR] recipe=renderer_text_only callable={name} reason={fault}")
                    return fallback
            raise

    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            return await _async_logic(*args, **kwargs)
        async_wrapper._ea_renderer_wrapped = True  # type: ignore[attr-defined]
        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args, **kwargs):
        return _sync_logic(*args, **kwargs)
    sync_wrapper._ea_renderer_wrapped = True  # type: ignore[attr-defined]
    return sync_wrapper


def discover_renderer_targets(module: Any) -> list[str]:
    targets: list[str] = []
    for name in dir(module):
        if name.startswith("_") and "markupgo" not in name.lower():
            continue
        obj = getattr(module, name, None)
        if not callable(obj):
            continue

        lowered = name.lower()
        if "markupgo" in lowered or lowered in {"render_markupgo", "call_markupgo", "render_briefing_markupgo"}:
            targets.append(name)
            continue

        try:
            src = inspect.getsource(obj)
        except Exception:
            continue

        lowered_src = src.lower()
        if "markupgo" in lowered_src or "source/data/id" in lowered_src or "invalid template id" in lowered_src:
            targets.append(name)

    return sorted(set(targets))


def patch_renderer_module(module: Any) -> list[str]:
    key = id(module)
    if key in _PATCHED_MODULE_IDS:
        return discover_renderer_targets(module)

    wrapped: list[str] = []
    for name in discover_renderer_targets(module):
        obj = getattr(module, name, None)
        if callable(obj):
            setattr(module, name, _wrap_renderer_callable(name, obj))
            wrapped.append(name)

    _PATCHED_MODULE_IDS.add(key)
    return wrapped


def install_renderer_repair(module: Any | None = None) -> list[str]:
    if module is None:
        import app.briefings as module  # type: ignore
    wrapped = patch_renderer_module(module)
    overrides = discover_known_good_template_ids()
    print(f"[EA RENDER REPAIR] installed wrapped={wrapped} template_overrides={[ _mask(v) for v in overrides ] or ['none']}")
    return wrapped
