from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .json_data import UnexpectedJsonError, json_array, json_object
from .workflow import Action, OutputRef, new_action_uuid

if TYPE_CHECKING:
    from collections.abc import Callable

    from .json_data import JsonObject, JsonValue
    from .workflow import Parameters, ParameterValue


@dataclass
class ActionContext:
    group_identifiers: dict[str, str] = field(default_factory=dict)
    group_end_identifiers: dict[str, str] = field(default_factory=dict)

    def group_identifier(self, group: str, end_identifier: str | None = None) -> str:
        if end_identifier is not None:
            existing_end_identifier = self.group_end_identifiers.get(group)
            if existing_end_identifier is None:
                self.group_end_identifiers[group] = end_identifier
            elif existing_end_identifier != end_identifier:
                raise ValueError(f"Control-flow group {group!r} has conflicting action kinds")

        existing = self.group_identifiers.get(group)
        if existing is not None:
            return existing

        generated = new_action_uuid()
        self.group_identifiers[group] = generated
        return generated

    def group_end_identifier(self, group: str, default: str) -> str:
        return self.group_end_identifiers.get(group, default)


def spec_id(spec: JsonObject) -> str | None:
    value = spec.get("id")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("Action field 'id' must be a non-empty string")
    return value


def spec_group(spec: JsonObject) -> str:
    group = spec.get("group") or spec.get("id")
    if not isinstance(group, str) or not group:
        raise ValueError("Control-flow action must include non-empty 'id' or 'group'")
    return group


def spec_object(spec: JsonObject, key: str) -> JsonObject:
    return json_object(spec.get(key) or {}, f"Action field {key!r} must be an object")


def spec_count(spec: JsonObject) -> int:
    count = spec["count"]
    if not isinstance(count, int):
        raise UnexpectedJsonError("Action field 'count' must be an integer")
    return int(count)


@dataclass(frozen=True)
class Comparison:
    condition: str = "Equals"
    input_value: JsonValue = None
    compare_value: JsonValue = None


def recipe_value(value: JsonValue) -> ParameterValue:
    if isinstance(value, dict):
        ref = value.get("ref")
        if isinstance(ref, str):
            output_name = value.get("output_name")
            if output_name is not None and not isinstance(output_name, str):
                raise ValueError("Reference field 'output_name' must be a string")
            return OutputRef(ref, output_name)
        return {key: recipe_value(child) for key, child in value.items()}

    if isinstance(value, list):
        return [recipe_value(child) for child in value]

    return value


def comment(text: str, recipe_id: str | None = None) -> Action:
    return Action(
        identifier="is.workflow.actions.comment",
        parameters={"WFCommentActionText": text},
        recipe_id=recipe_id,
        output_name="Comment",
    )


def text(value: JsonValue, recipe_id: str | None = None) -> Action:
    return Action(
        identifier="is.workflow.actions.gettext",
        parameters={"WFTextActionText": recipe_value(value)},
        recipe_id=recipe_id,
        output_name="Text",
    )


def url(value: str, recipe_id: str | None = None) -> Action:
    return Action(
        identifier="is.workflow.actions.url",
        parameters={"WFURLActionURL": value},
        recipe_id=recipe_id,
        output_name="URL",
    )


def open_url(recipe_id: str | None = None) -> Action:
    return Action(identifier="is.workflow.actions.openurl", recipe_id=recipe_id)


def show_result(value: JsonValue = None, recipe_id: str | None = None) -> Action:
    parameters: Parameters = {}
    if value is not None:
        parameters["Text"] = recipe_value(value)
    return Action(
        identifier="is.workflow.actions.showresult",
        parameters=parameters,
        recipe_id=recipe_id,
    )


def set_clipboard(value: JsonValue = None, recipe_id: str | None = None) -> Action:
    parameters: Parameters = {}
    if value is not None:
        parameters["WFInput"] = recipe_value(value)
    return Action(
        identifier="is.workflow.actions.setclipboard",
        parameters=parameters,
        recipe_id=recipe_id,
    )


def ask_for_input(
    prompt: str,
    input_type: str = "Text",
    recipe_id: str | None = None,
) -> Action:
    return Action(
        identifier="is.workflow.actions.ask",
        parameters={
            "WFAskActionPrompt": prompt,
            "WFInputType": input_type,
        },
        recipe_id=recipe_id,
        output_name="Provided Input",
    )


def notification(
    title: JsonValue,
    body: JsonValue = None,
    recipe_id: str | None = None,
) -> Action:
    parameters: Parameters = {
        "WFNotificationActionSound": True,
        "WFNotificationActionTitle": text_token_value(recipe_value(title)),
    }
    if body is not None:
        parameters["WFNotificationActionBody"] = text_token_value(recipe_value(body))
    return Action(
        identifier="is.workflow.actions.notification",
        parameters=parameters,
        recipe_id=recipe_id,
    )


def alert(
    title: JsonValue,
    message: JsonValue = None,
    *,
    show_cancel: bool = True,
    recipe_id: str | None = None,
) -> Action:
    parameters: Parameters = {
        "WFAlertActionTitle": text_token_value(recipe_value(title)),
        "WFAlertActionCancelButtonShown": show_cancel,
    }
    if message is not None:
        parameters["WFAlertActionMessage"] = text_token_value(recipe_value(message))
    return Action(
        identifier="is.workflow.actions.alert",
        parameters=parameters,
        recipe_id=recipe_id,
    )


def current_date(recipe_id: str | None = None) -> Action:
    return Action(
        identifier="is.workflow.actions.date",
        recipe_id=recipe_id,
        output_name="Date",
    )


def dictionary(items: JsonObject, recipe_id: str | None = None) -> Action:
    return Action(
        identifier="is.workflow.actions.dictionary",
        parameters={"WFItems": dictionary_field_value(items)},
        recipe_id=recipe_id,
        output_name="Dictionary",
    )


def dictionary_field_value(items: JsonObject) -> Parameters:
    return {
        "Value": {
            "WFDictionaryFieldValueItems": dictionary_items(items),
        },
        "WFSerializationType": "WFDictionaryFieldValue",
    }


def text_token_value(value: ParameterValue) -> ParameterValue:
    if isinstance(value, OutputRef):
        return value
    return {
        "Value": {
            "attachmentsByRange": {},
            "string": str(value),
        },
        "WFSerializationType": "WFTextTokenString",
    }


def maybe_text_token(value: JsonValue) -> ParameterValue:
    resolved = recipe_value(value)
    if isinstance(resolved, OutputRef):
        return text_token_value(resolved)
    return resolved


def dictionary_items(items: JsonObject) -> list[ParameterValue]:
    return [
        {
            "WFItemType": 0,
            "WFKey": key,
            "WFValue": text_token_value(recipe_value(value)),
        }
        for key, value in items.items()
    ]


def raw(
    identifier: str,
    parameters: JsonObject | None = None,
    recipe_id: str | None = None,
) -> Action:
    resolved = recipe_value(parameters or {})
    if not isinstance(resolved, dict):
        raise UnexpectedJsonError("Raw action 'parameters' must be an object, not a reference")
    return Action(
        identifier=identifier,
        parameters=dict(resolved),
        recipe_id=recipe_id,
    )


def if_start(
    context: ActionContext,
    group: str,
    comparison: Comparison | None = None,
    recipe_id: str | None = None,
) -> Action:
    comparison = comparison or Comparison()
    parameters: Parameters = {
        "GroupingIdentifier": context.group_identifier(
            group,
            "is.workflow.actions.conditional",
        ),
        "WFCondition": comparison.condition,
        "WFControlFlowMode": 0,
    }
    if comparison.input_value is not None:
        parameters["WFInput"] = recipe_value(comparison.input_value)
    if comparison.compare_value is not None:
        parameters["WFConditionalActionString"] = text_token_value(
            recipe_value(comparison.compare_value)
        )
    return Action(
        identifier="is.workflow.actions.conditional",
        parameters=parameters,
        recipe_id=recipe_id,
        output_name="If Result",
    )


def otherwise(context: ActionContext, group: str) -> Action:
    return Action(
        identifier="is.workflow.actions.conditional",
        parameters={
            "GroupingIdentifier": context.group_identifier(
                group,
                "is.workflow.actions.conditional",
            ),
            "WFControlFlowMode": 1,
        },
    )


def end_if(context: ActionContext, group: str) -> Action:
    return Action(
        identifier="is.workflow.actions.conditional",
        parameters={
            "GroupingIdentifier": context.group_identifier(
                group,
                "is.workflow.actions.conditional",
            ),
            "WFControlFlowMode": 2,
        },
    )


def repeat_count(context: ActionContext, group: str, count: int, recipe_id: str | None) -> Action:
    return Action(
        identifier="is.workflow.actions.repeat.count",
        parameters={
            "GroupingIdentifier": context.group_identifier(
                group,
                "is.workflow.actions.repeat.count",
            ),
            "WFControlFlowMode": 0,
            "WFRepeatCount": count,
        },
        recipe_id=recipe_id,
        output_name="Repeat Results",
    )


def repeat_each(
    context: ActionContext,
    group: str,
    input_value: JsonValue,
    recipe_id: str | None,
) -> Action:
    parameters: Parameters = {
        "GroupingIdentifier": context.group_identifier(
            group,
            "is.workflow.actions.repeat.each",
        ),
        "WFControlFlowMode": 0,
    }
    if input_value is not None:
        parameters["WFInput"] = recipe_value(input_value)
    return Action(
        identifier="is.workflow.actions.repeat.each",
        parameters=parameters,
        recipe_id=recipe_id,
        output_name="Repeat Results",
    )


def end_repeat(context: ActionContext, group: str) -> Action:
    return Action(
        identifier=context.group_end_identifier(group, "is.workflow.actions.repeat.count"),
        parameters={
            "GroupingIdentifier": context.group_identifier(group),
            "WFControlFlowMode": 2,
        },
    )


def choose_from_menu(
    context: ActionContext,
    group: str,
    items: list[str],
    prompt: JsonValue,
    recipe_id: str | None,
) -> Action:
    parameters: Parameters = {
        "GroupingIdentifier": context.group_identifier(
            group,
            "is.workflow.actions.choosefrommenu",
        ),
        "WFControlFlowMode": 0,
        "WFMenuItems": [*items],
    }
    if prompt is not None:
        parameters["WFMenuPrompt"] = prompt
    return Action(
        identifier="is.workflow.actions.choosefrommenu",
        parameters=parameters,
        recipe_id=recipe_id,
        output_name="Menu Result",
    )


def menu_item(context: ActionContext, group: str, title: str) -> Action:
    return Action(
        identifier="is.workflow.actions.choosefrommenu",
        parameters={
            "GroupingIdentifier": context.group_identifier(
                group,
                "is.workflow.actions.choosefrommenu",
            ),
            "WFControlFlowMode": 1,
            "WFMenuItemTitle": title,
        },
    )


def end_menu(context: ActionContext, group: str) -> Action:
    return Action(
        identifier="is.workflow.actions.choosefrommenu",
        parameters={
            "GroupingIdentifier": context.group_identifier(
                group,
                "is.workflow.actions.choosefrommenu",
            ),
            "WFControlFlowMode": 2,
        },
    )


def get_contents_of_url(
    url_value: JsonValue = None,
    method: str = "GET",
    headers: JsonObject | None = None,
    recipe_id: str | None = None,
) -> Action:
    parameters: Parameters = {
        "ShowHeaders": bool(headers),
        "WFHTTPMethod": method,
    }
    if url_value is not None:
        parameters["WFURL"] = maybe_text_token(url_value)
    if headers:
        parameters["WFHTTPHeaders"] = dictionary_field_value(headers)
    return Action(
        identifier="is.workflow.actions.downloadurl",
        parameters=parameters,
        recipe_id=recipe_id,
        output_name="Contents of URL",
    )


def get_dictionary_from_input(input_value: JsonValue = None, recipe_id: str | None = None) -> Action:
    parameters: Parameters = {}
    if input_value is not None:
        parameters["WFInput"] = recipe_value(input_value)
    return Action(
        identifier="is.workflow.actions.detect.dictionary",
        parameters=parameters,
        recipe_id=recipe_id,
        output_name="Dictionary",
    )


def get_dictionary_value(
    key: JsonValue,
    input_value: JsonValue = None,
    get_type: str = "Value",
    recipe_id: str | None = None,
) -> Action:
    parameters: Parameters = {
        "WFDictionaryKey": text_token_value(recipe_value(key)),
        "WFGetDictionaryValueType": get_type,
    }
    if input_value is not None:
        parameters["WFInput"] = recipe_value(input_value)
    return Action(
        identifier="is.workflow.actions.getvalueforkey",
        parameters=parameters,
        recipe_id=recipe_id,
        output_name="Dictionary Value",
    )


def set_dictionary_value(
    key: JsonValue,
    value: JsonValue,
    input_value: JsonValue = None,
    recipe_id: str | None = None,
) -> Action:
    parameters: Parameters = {
        "WFDictionaryKey": text_token_value(recipe_value(key)),
        "WFDictionaryValue": text_token_value(recipe_value(value)),
    }
    if input_value is not None:
        parameters["WFDictionary"] = recipe_value(input_value)
    return Action(
        identifier="is.workflow.actions.setvalueforkey",
        parameters=parameters,
        recipe_id=recipe_id,
        output_name="Dictionary",
    )


ACTION_FACTORIES: dict[str, Callable[[JsonObject], Action]] = {
    "alert": lambda spec: alert(
        spec["title"],
        spec.get("message"),
        show_cancel=bool(spec.get("show_cancel", True)),
        recipe_id=spec_id(spec),
    ),
    "ask_for_input": lambda spec: ask_for_input(
        str(spec["prompt"]),
        str(spec.get("input_type", "Text")),
        spec_id(spec),
    ),
    "comment": lambda spec: comment(str(spec["text"]), spec_id(spec)),
    "current_date": lambda spec: current_date(spec_id(spec)),
    "dictionary": lambda spec: dictionary(spec_object(spec, "items"), spec_id(spec)),
    "get_contents_of_url": lambda spec: get_contents_of_url(
        spec.get("url"),
        str(spec.get("method", "GET")),
        spec_object(spec, "headers"),
        spec_id(spec),
    ),
    "get_dictionary_from_input": lambda spec: get_dictionary_from_input(
        spec.get("input"),
        spec_id(spec),
    ),
    "get_dictionary_value": lambda spec: get_dictionary_value(
        spec["key"],
        spec.get("input"),
        str(spec.get("get", "Value")),
        spec_id(spec),
    ),
    "notification": lambda spec: notification(
        spec["title"],
        spec.get("body"),
        spec_id(spec),
    ),
    "open_url": lambda spec: open_url(spec_id(spec)),
    "raw": lambda spec: raw(
        str(spec["identifier"]),
        spec_object(spec, "parameters"),
        spec_id(spec),
    ),
    "set_clipboard": lambda spec: set_clipboard(spec.get("input"), spec_id(spec)),
    "set_dictionary_value": lambda spec: set_dictionary_value(
        spec["key"],
        spec["value"],
        spec.get("input"),
        spec_id(spec),
    ),
    "show_result": lambda spec: show_result(spec.get("text"), spec_id(spec)),
    "text": lambda spec: text(spec["text"], spec_id(spec)),
    "url": lambda spec: url(str(spec["url"]), spec_id(spec)),
}

CONTEXT_ACTION_FACTORIES: dict[str, Callable[[JsonObject, ActionContext], Action]] = {
    "choose_from_menu": lambda spec, context: choose_from_menu(
        context,
        spec_group(spec),
        [
            str(item)
            for item in json_array(spec["items"], "Action field 'items' must be an array")
        ],
        spec.get("prompt"),
        spec_id(spec),
    ),
    "end_if": lambda spec, context: end_if(context, spec_group(spec)),
    "end_menu": lambda spec, context: end_menu(context, spec_group(spec)),
    "end_repeat": lambda spec, context: end_repeat(context, spec_group(spec)),
    "if": lambda spec, context: if_start(
        context,
        spec_group(spec),
        Comparison(
            str(spec.get("condition", "Equals")),
            spec.get("input"),
            spec.get("value"),
        ),
        spec_id(spec),
    ),
    "menu_item": lambda spec, context: menu_item(
        context,
        spec_group(spec),
        str(spec["title"]),
    ),
    "otherwise": lambda spec, context: otherwise(context, spec_group(spec)),
    "repeat_count": lambda spec, context: repeat_count(
        context,
        spec_group(spec),
        spec_count(spec),
        spec_id(spec),
    ),
    "repeat_each": lambda spec, context: repeat_each(
        context,
        spec_group(spec),
        spec.get("input"),
        spec_id(spec),
    ),
}


def action_from_recipe(spec: JsonObject, context: ActionContext | None = None) -> Action:
    kind = spec.get("kind")
    if not isinstance(kind, str):
        raise UnexpectedJsonError("Action is missing string field 'kind'")

    context = context or ActionContext()
    context_factory = CONTEXT_ACTION_FACTORIES.get(kind)
    if context_factory is not None:
        return context_factory(spec, context)

    factory = ACTION_FACTORIES.get(kind)
    if factory is None:
        supported = ", ".join(sorted(ACTION_FACTORIES | CONTEXT_ACTION_FACTORIES))
        raise ValueError(f"Unsupported action kind {kind!r}. Supported: {supported}")

    return factory(spec)
