from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .actions import ACTION_FACTORIES, CONTEXT_ACTION_FACTORIES

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from .json_data import JsonObject, JsonValue

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


class ValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors: list[str] = errors


@dataclass
class SeenActions:
    ids: set[str]
    groups: dict[str, str]


def validate_recipe(recipe: JsonValue) -> None:
    errors = list(iter_recipe_errors(recipe))
    if errors:
        raise ValidationError(errors)


def iter_recipe_errors(recipe: JsonValue) -> Iterable[str]:
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

    seen = SeenActions(ids=set(), groups={})
    for index, action in enumerate(actions):
        yield from iter_action_errors(f"actions[{index}]", action, seen)


def iter_action_errors(prefix: str, action: JsonValue, seen: SeenActions) -> Iterable[str]:
    if not isinstance(action, dict):
        yield f"{prefix} must be an object"
        return

    kind = action.get("kind")
    if not isinstance(kind, str):
        yield f"{prefix}.kind must be a string"
        return

    if kind not in SUPPORTED_KINDS:
        supported = ", ".join(sorted(SUPPORTED_KINDS))
        yield f"{prefix}.kind {kind!r} is unsupported. Supported: {supported}"
        return

    for field in REQUIRED_FIELDS.get(kind, ()):
        if field not in action:
            yield f"{prefix} ({kind}) is missing required field {field!r}"

    action_id = action.get("id")
    id_error = action_id_error(prefix, action_id, seen.ids)
    if id_error is not None:
        yield id_error

    yield from iter_group_member_errors(prefix, kind, action, seen.groups)
    yield from iter_kind_errors(prefix, kind, action)
    yield from iter_ref_errors(prefix, action, seen.ids)

    if isinstance(action_id, str) and id_error is None:
        seen.ids.add(action_id)
        start_group_kind = GROUP_START_KINDS.get(kind)
        if start_group_kind is not None:
            seen.groups[action_id] = start_group_kind


def action_id_error(prefix: str, action_id: JsonValue, seen_ids: set[str]) -> str | None:
    if action_id is None:
        return None
    if not isinstance(action_id, str) or not action_id:
        return f"{prefix}.id must be a non-empty string"
    if action_id in seen_ids:
        return f"{prefix}.id {action_id!r} is duplicated"
    return None


def iter_group_member_errors(
    prefix: str, kind: str, action: JsonObject, seen_groups: dict[str, str]
) -> Iterable[str]:
    member_group_kind = GROUP_MEMBER_KINDS.get(kind)
    if member_group_kind is None:
        return
    group = action.get("group")
    if not isinstance(group, str) or not group:
        yield f"{prefix} ({kind}) must include non-empty field 'group'"
    elif seen_groups.get(group) != member_group_kind:
        yield f"{prefix}.group {group!r} does not reference an open {member_group_kind} group"


def iter_kind_errors(prefix: str, kind: str, action: JsonObject) -> Iterable[str]:
    kind_errors = KIND_ERRORS.get(kind)
    if kind_errors is not None:
        yield from kind_errors(prefix, action)


def iter_choose_from_menu_errors(prefix: str, action: JsonObject) -> Iterable[str]:
    items = action.get("items")
    if not isinstance(items, list) or not items or not all(isinstance(item, str) for item in items):
        yield f"{prefix}.items must be a non-empty array of strings"


def iter_dictionary_errors(prefix: str, action: JsonObject) -> Iterable[str]:
    if not isinstance(action.get("items"), dict):
        yield f"{prefix}.items must be an object"


def iter_get_contents_of_url_errors(prefix: str, action: JsonObject) -> Iterable[str]:
    method = action.get("method", "GET")
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        yield f"{prefix}.method must be one of GET, POST, PUT, PATCH, DELETE"
    headers = action.get("headers")
    if headers is not None and not isinstance(headers, dict):
        yield f"{prefix}.headers must be an object"


def iter_get_dictionary_value_errors(prefix: str, action: JsonObject) -> Iterable[str]:
    get_type = action.get("get", "Value")
    if get_type not in {"Value", "All Keys", "All Values"}:
        yield f"{prefix}.get must be one of Value, All Keys, All Values"


def iter_raw_errors(prefix: str, action: JsonObject) -> Iterable[str]:
    if not isinstance(action.get("identifier"), str) or not action.get("identifier"):
        yield f"{prefix}.identifier must be a non-empty string"
    parameters = action.get("parameters")
    if parameters is not None and not isinstance(parameters, dict):
        yield f"{prefix}.parameters must be an object"


def iter_repeat_count_errors(prefix: str, action: JsonObject) -> Iterable[str]:
    count = action.get("count")
    if not isinstance(count, int) or count < 1:
        yield f"{prefix}.count must be a positive integer"


KIND_ERRORS: dict[str, Callable[[str, JsonObject], Iterable[str]]] = {
    "choose_from_menu": iter_choose_from_menu_errors,
    "dictionary": iter_dictionary_errors,
    "get_contents_of_url": iter_get_contents_of_url_errors,
    "get_dictionary_value": iter_get_dictionary_value_errors,
    "raw": iter_raw_errors,
    "repeat_count": iter_repeat_count_errors,
}


def iter_ref_errors(prefix: str, value: JsonValue, seen_ids: set[str]) -> Iterable[str]:
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
