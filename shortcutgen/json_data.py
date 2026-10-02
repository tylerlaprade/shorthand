from __future__ import annotations

import json
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from collections.abc import Callable

JsonValue = Union[dict[str, "JsonValue"], list["JsonValue"], str, int, float, bool, None]
JsonObject = dict[str, JsonValue]

parse_json: Callable[[str], JsonValue] = json.loads


class UnexpectedJsonError(ValueError):
    pass


def json_object(value: JsonValue, message: str) -> JsonObject:
    if not isinstance(value, dict):
        raise UnexpectedJsonError(message)
    return value


def json_array(value: JsonValue, message: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise UnexpectedJsonError(message)
    return value
