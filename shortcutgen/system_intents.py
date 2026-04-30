from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_ACTIONS_INTENTDEFINITION = Path(
    "/System/Library/PrivateFrameworks/WorkflowKit.framework/"
    "PlugIns/ShortcutsIntents.appex/Contents/Resources/Base.lproj/Actions.intentdefinition"
)


def load_intentdefinition(path: Path = DEFAULT_ACTIONS_INTENTDEFINITION) -> dict[str, Any]:
    result = subprocess.run(
        ["plutil", "-convert", "json", "-o", "-", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError(f"Intent definition at {path} did not contain a JSON object")
    return data


def system_intent_catalog(
    path: Path = DEFAULT_ACTIONS_INTENTDEFINITION,
) -> dict[str, Any]:
    return catalog_from_intentdefinition(load_intentdefinition(path), path)


def catalog_from_intentdefinition(
    definition: dict[str, Any],
    source_path: Path | None = None,
) -> dict[str, Any]:
    enums = {enum["INEnumName"]: compact_enum(enum) for enum in definition.get("INEnums", [])}
    intents = [
        compact_intent(intent, enums)
        for intent in definition.get("INIntents", [])
        if isinstance(intent, dict)
    ]
    intents.sort(key=lambda intent: intent["name"])

    return {
        "source_path": str(source_path) if source_path is not None else None,
        "namespace": definition.get("INIntentDefinitionNamespace"),
        "intent_count": len(intents),
        "intents": intents,
    }


def compact_enum(enum: dict[str, Any]) -> dict[str, Any]:
    values = []
    for value in enum.get("INEnumValues", []):
        if not isinstance(value, dict):
            continue
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


def compact_intent(intent: dict[str, Any], enums: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "name": intent.get("INIntentName"),
        "title": intent.get("INIntentTitle"),
        "description": intent.get("INIntentDescription"),
        "category": intent.get("INIntentCategory"),
        "verb": intent.get("INIntentVerb"),
        "input": intent.get("INIntentInput"),
        "output": (intent.get("INIntentResponse") or {}).get("INIntentResponseOutput"),
        "parameters": [
            compact_parameter(parameter, enums)
            for parameter in intent.get("INIntentParameters", [])
            if isinstance(parameter, dict)
        ],
    }


def compact_parameter(
    parameter: dict[str, Any],
    enums: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    enum_name = parameter.get("INIntentParameterEnumType")
    compact: dict[str, Any] = {
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
