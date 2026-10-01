from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .json_data import json_object, parse_json

if TYPE_CHECKING:
    from .json_data import JsonObject, JsonValue

DEFAULT_ACTIONS_INTENTDEFINITION = Path(
    "/System/Library/PrivateFrameworks/WorkflowKit.framework/"
    "PlugIns/ShortcutsIntents.appex/Contents/Resources/Base.lproj/Actions.intentdefinition"
)


def load_intentdefinition(path: Path = DEFAULT_ACTIONS_INTENTDEFINITION) -> JsonObject:
    result = subprocess.run(
        ["plutil", "-convert", "json", "-o", "-", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json_object(
        parse_json(result.stdout),
        f"Intent definition at {path} did not contain a JSON object",
    )


def system_intent_catalog(
    path: Path = DEFAULT_ACTIONS_INTENTDEFINITION,
) -> JsonObject:
    return catalog_from_intentdefinition(load_intentdefinition(path), path)


def objects_in(value: JsonValue) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def catalog_from_intentdefinition(
    definition: JsonObject,
    source_path: Path | None = None,
) -> JsonObject:
    enums = {
        str(enum["INEnumName"]): compact_enum(enum)
        for enum in objects_in(definition.get("INEnums", []))
    }
    intents: list[JsonObject] = [
        compact_intent(intent, enums) for intent in objects_in(definition.get("INIntents", []))
    ]
    intents.sort(key=lambda intent: str(intent["name"]))

    return {
        "source_path": str(source_path) if source_path is not None else None,
        "namespace": definition.get("INIntentDefinitionNamespace"),
        "intent_count": len(intents),
        "intents": [*intents],
    }


def compact_enum(enum: JsonObject) -> JsonObject:
    values: list[JsonValue] = []
    for value in objects_in(enum.get("INEnumValues", [])):
        name = value.get("INEnumValueName")
        if name == "unknown":
            continue
        values.append(
            {
                "name": name,
                "display": value.get("INEnumValueDisplayName"),
                "index": value.get("INEnumValueIndex"),
            }
        )

    return {
        "name": enum.get("INEnumName"),
        "display": enum.get("INEnumDisplayName"),
        "values": values,
    }


def compact_intent(intent: JsonObject, enums: dict[str, JsonObject]) -> JsonObject:
    response = json_object(
        intent.get("INIntentResponse") or {}, "Intent field 'INIntentResponse' must be an object"
    )
    return {
        "name": intent.get("INIntentName"),
        "title": intent.get("INIntentTitle"),
        "description": intent.get("INIntentDescription"),
        "category": intent.get("INIntentCategory"),
        "verb": intent.get("INIntentVerb"),
        "input": intent.get("INIntentInput"),
        "output": response.get("INIntentResponseOutput"),
        "parameters": [
            compact_parameter(parameter, enums)
            for parameter in objects_in(intent.get("INIntentParameters", []))
        ],
    }


def compact_parameter(
    parameter: JsonObject,
    enums: dict[str, JsonObject],
) -> JsonObject:
    enum_name = parameter.get("INIntentParameterEnumType")
    compact: JsonObject = {
        "name": parameter.get("INIntentParameterName"),
        "display": parameter.get("INIntentParameterDisplayName"),
        "type": parameter.get("INIntentParameterType"),
        "object_type": parameter.get("INIntentParameterObjectType"),
        "enum_type": enum_name,
        "multiple": bool(parameter.get("INIntentParameterSupportsMultipleValues", False)),
        "configurable": bool(parameter.get("INIntentParameterConfigurable", False)),
    }

    metadata = parameter.get("INIntentParameterMetadata")
    if isinstance(metadata, dict):
        default_value = metadata.get("INIntentParameterMetadataDefaultValue")
        if default_value is not None:
            compact["default"] = default_value

    if isinstance(enum_name, str) and enum_name in enums:
        compact["enum_values"] = enums[enum_name]["values"]

    return {key: value for key, value in compact.items() if value is not None}
