from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .actions import ACTION_FACTORIES, CONTEXT_ACTION_FACTORIES


SUPPORTED_KINDS = frozenset(ACTION_FACTORIES) | frozenset(CONTEXT_ACTION_FACTORIES)

REQUIRED_FIELDS = {
    "alert": ("title",),
    "ask_for_input": ("prompt",),
    "choose_from_menu": ("id", "items"),
    "comment": ("text",),
    "dictionary": ("items",),
    "get_dictionary_value": ("key",),
    "if": ("id",),
    "menu_item": ("group", "title"),
    "notification": ("title",),
    "raw": ("identifier",),
    "repeat_count": ("id", "count"),
    "repeat_each": ("id",),
    "set_dictionary_value": ("key", "value"),
    "text": ("text",),
    "url": ("url",),
}

GROUP_START_KINDS = {
    "choose_from_menu": "menu",
    "if": "if",
    "repeat_count": "repeat",
    "repeat_each": "repeat",
}

GROUP_MEMBER_KINDS = {
    "end_if": "if",
    "end_menu": "menu",
    "end_repeat": "repeat",
    "menu_item": "menu",
    "otherwise": "if",
}


@dataclass(frozen=True)
class ValidationError(Exception):
    errors: list[str]

    def __str__(self) -> str:
        return "\n".join(self.errors)


def validate_recipe(recipe: dict[str, Any]) -> None:
    errors = list(iter_recipe_errors(recipe))
    if errors:
        raise ValidationError(errors)


def iter_recipe_errors(recipe: dict[str, Any]) -> Iterable[str]:
    if not isinstance(recipe, dict):
        yield "Recipe root must be a JSON object"
        return

    unsupported = recipe.get("unsupported")
    if unsupported is not None and not isinstance(unsupported, bool):
        yield "Recipe field 'unsupported' must be a boolean"

    if unsupported is True:
        reason = recipe.get("reason")
        if not isinstance(reason, str) or not reason:
            yield "Unsupported recipe must include non-empty string field 'reason'"
        yield "Recipe is marked unsupported and must not be compiled"
        return

    if not isinstance(recipe.get("name"), str) or not recipe.get("name"):
        yield "Recipe field 'name' must be a non-empty string"

    actions = recipe.get("actions")
    if not isinstance(actions, list) or not actions:
        yield "Recipe field 'actions' must be a non-empty array"
        return

    seen_ids: set[str] = set()
    seen_groups: dict[str, str] = {}

    for index, action in enumerate(actions):
        prefix = f"actions[{index}]"
        if not isinstance(action, dict):
            yield f"{prefix} must be an object"
            continue

        kind = action.get("kind")
        if not isinstance(kind, str):
            yield f"{prefix}.kind must be a string"
            continue

        if kind not in SUPPORTED_KINDS:
            supported = ", ".join(sorted(SUPPORTED_KINDS))
            yield f"{prefix}.kind {kind!r} is unsupported. Supported: {supported}"
            continue

        for field in REQUIRED_FIELDS.get(kind, ()):
            if field not in action:
                yield f"{prefix} ({kind}) is missing required field {field!r}"

        action_id = action.get("id")
        valid_action_id: str | None = None
        if action_id is not None:
            if not isinstance(action_id, str) or not action_id:
                yield f"{prefix}.id must be a non-empty string"
            elif action_id in seen_ids:
                yield f"{prefix}.id {action_id!r} is duplicated"
            else:
                valid_action_id = action_id

        member_group_kind = GROUP_MEMBER_KINDS.get(kind)
        if member_group_kind is not None:
            group = action.get("group")
            if not isinstance(group, str) or not group:
                yield f"{prefix} ({kind}) must include non-empty field 'group'"
            elif seen_groups.get(group) != member_group_kind:
                yield f"{prefix}.group {group!r} does not reference an open {member_group_kind} group"

        yield from iter_kind_errors(prefix, kind, action)
        yield from iter_ref_errors(prefix, action, seen_ids)

        if valid_action_id is not None:
            seen_ids.add(valid_action_id)

            start_group_kind = GROUP_START_KINDS.get(kind)
            if start_group_kind is not None:
                seen_groups[valid_action_id] = start_group_kind


def iter_kind_errors(prefix: str, kind: str, action: dict[str, Any]) -> Iterable[str]:
    if kind == "choose_from_menu":
        items = action.get("items")
        if not isinstance(items, list) or not items or not all(isinstance(item, str) for item in items):
            yield f"{prefix}.items must be a non-empty array of strings"

    if kind == "dictionary":
        if not isinstance(action.get("items"), dict):
            yield f"{prefix}.items must be an object"

    if kind == "get_contents_of_url":
        method = action.get("method", "GET")
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            yield f"{prefix}.method must be one of GET, POST, PUT, PATCH, DELETE"
        headers = action.get("headers")
        if headers is not None and not isinstance(headers, dict):
            yield f"{prefix}.headers must be an object"

    if kind == "get_dictionary_value":
        get_type = action.get("get", "Value")
        if get_type not in {"Value", "All Keys", "All Values"}:
            yield f"{prefix}.get must be one of Value, All Keys, All Values"

    if kind == "raw":
        if not isinstance(action.get("identifier"), str) or not action.get("identifier"):
            yield f"{prefix}.identifier must be a non-empty string"
        parameters = action.get("parameters")
        if parameters is not None and not isinstance(parameters, dict):
            yield f"{prefix}.parameters must be an object"

    if kind == "repeat_count":
        count = action.get("count")
        if not isinstance(count, int) or count < 1:
            yield f"{prefix}.count must be a positive integer"


def iter_ref_errors(prefix: str, value: Any, seen_ids: set[str]) -> Iterable[str]:
    if isinstance(value, dict):
        ref = value.get("ref")
        if ref is not None:
            if not isinstance(ref, str) or not ref:
                yield f"{prefix}.ref must be a non-empty string"
            elif ref not in seen_ids:
                yield f"{prefix}.ref {ref!r} must reference an earlier action id"

        output_name = value.get("output_name")
        if output_name is not None and not isinstance(output_name, str):
            yield f"{prefix}.output_name must be a string"

        for key, child in value.items():
            if key in {"ref", "output_name"}:
                continue
            yield from iter_ref_errors(f"{prefix}.{key}", child, seen_ids)
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_ref_errors(f"{prefix}[{index}]", child, seen_ids)
