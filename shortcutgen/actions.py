from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .workflow import Action, OutputRef, new_action_uuid


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


def spec_id(spec: dict[str, Any]) -> str | None:
    value = spec.get("id")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("Action field 'id' must be a non-empty string")
    return value


def spec_group(spec: dict[str, Any]) -> str:
    group = spec.get("group") or spec.get("id")
    if not isinstance(group, str) or not group:
        raise ValueError("Control-flow action must include non-empty 'id' or 'group'")
    return group


def recipe_value(value: Any) -> Any:
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


def text(value: Any, recipe_id: str | None = None) -> Action:
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


def show_result(value: Any | None = None, recipe_id: str | None = None) -> Action:
    parameters = {}
    if value is not None:
        parameters["Text"] = recipe_value(value)
    return Action(
        identifier="is.workflow.actions.showresult",
        parameters=parameters,
        recipe_id=recipe_id,
    )


def set_clipboard(value: Any | None = None, recipe_id: str | None = None) -> Action:
    parameters = {}
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
    title: Any,
    body: Any | None = None,
    recipe_id: str | None = None,
) -> Action:
    parameters = {
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
    title: Any,
    message: Any | None = None,
    show_cancel: bool = True,
    recipe_id: str | None = None,
) -> Action:
    parameters = {
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


def dictionary(items: dict[str, Any], recipe_id: str | None = None) -> Action:
    return Action(
        identifier="is.workflow.actions.dictionary",
        parameters={"WFItems": dictionary_field_value(items)},
        recipe_id=recipe_id,
        output_name="Dictionary",
    )


def dictionary_field_value(items: dict[str, Any]) -> dict[str, Any]:
    return {
        "Value": {
            "WFDictionaryFieldValueItems": dictionary_items(items),
        },
        "WFSerializationType": "WFDictionaryFieldValue",
    }


def text_token_value(value: Any) -> dict[str, Any]:
    if isinstance(value, OutputRef):
        return value
    return {
        "Value": {
            "attachmentsByRange": {},
            "string": str(value),
        },
        "WFSerializationType": "WFTextTokenString",
    }


def maybe_text_token(value: Any) -> Any:
    value = recipe_value(value)
    if isinstance(value, OutputRef):
        return text_token_value(value)
    return value


def dictionary_items(items: dict[str, Any]) -> list[dict[str, Any]]:
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
    parameters: dict[str, Any] | None = None,
    recipe_id: str | None = None,
) -> Action:
    return Action(
        identifier=identifier,
        parameters=recipe_value(parameters or {}),
        recipe_id=recipe_id,
    )


def if_start(
    context: ActionContext,
    group: str,
    condition: str = "Equals",
    input_value: Any | None = None,
    compare_value: Any | None = None,
    recipe_id: str | None = None,
) -> Action:
    parameters: dict[str, Any] = {
        "GroupingIdentifier": context.group_identifier(
            group,
            "is.workflow.actions.conditional",
        ),
        "WFCondition": condition,
        "WFControlFlowMode": 0,
    }
    if input_value is not None:
        parameters["WFInput"] = recipe_value(input_value)
    if compare_value is not None:
        parameters["WFConditionalActionString"] = text_token_value(recipe_value(compare_value))
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
    input_value: Any | None,
    recipe_id: str | None,
) -> Action:
    parameters: dict[str, Any] = {
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
    prompt: str | None,
    recipe_id: str | None,
) -> Action:
    parameters: dict[str, Any] = {
        "GroupingIdentifier": context.group_identifier(
            group,
            "is.workflow.actions.choosefrommenu",
        ),
        "WFControlFlowMode": 0,
        "WFMenuItems": items,
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
    url_value: Any | None = None,
    method: str = "GET",
    headers: dict[str, Any] | None = None,
    recipe_id: str | None = None,
) -> Action:
    parameters: dict[str, Any] = {
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


def get_dictionary_from_input(input_value: Any | None = None, recipe_id: str | None = None) -> Action:
    parameters = {}
    if input_value is not None:
        parameters["WFInput"] = recipe_value(input_value)
    return Action(
        identifier="is.workflow.actions.detect.dictionary",
        parameters=parameters,
        recipe_id=recipe_id,
        output_name="Dictionary",
    )


def get_dictionary_value(
    key: Any,
    input_value: Any | None = None,
    get_type: str = "Value",
    recipe_id: str | None = None,
) -> Action:
    parameters = {
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
    key: Any,
    value: Any,
    input_value: Any | None = None,
    recipe_id: str | None = None,
) -> Action:
    parameters = {
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


ACTION_FACTORIES = {
    "alert": lambda spec: alert(
        spec["title"],
        spec.get("message"),
        bool(spec.get("show_cancel", True)),
        spec_id(spec),
    ),
    "ask_for_input": lambda spec: ask_for_input(
        str(spec["prompt"]),
        str(spec.get("input_type", "Text")),
        spec_id(spec),
    ),
    "comment": lambda spec: comment(str(spec["text"]), spec_id(spec)),
    "current_date": lambda spec: current_date(spec_id(spec)),
    "dictionary": lambda spec: dictionary(spec.get("items") or {}, spec_id(spec)),
    "get_contents_of_url": lambda spec: get_contents_of_url(
        spec.get("url"),
        str(spec.get("method", "GET")),
        spec.get("headers"),
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
        spec.get("parameters") or {},
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

CONTEXT_ACTION_FACTORIES = {
    "choose_from_menu": lambda spec, context: choose_from_menu(
        context,
        spec_group(spec),
        [str(item) for item in spec["items"]],
        spec.get("prompt"),
        spec_id(spec),
    ),
    "end_if": lambda spec, context: end_if(context, spec_group(spec)),
    "end_menu": lambda spec, context: end_menu(context, spec_group(spec)),
    "end_repeat": lambda spec, context: end_repeat(context, spec_group(spec)),
    "if": lambda spec, context: if_start(
        context,
        spec_group(spec),
        str(spec.get("condition", "Equals")),
        spec.get("input"),
        spec.get("value"),
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
        int(spec["count"]),
        spec_id(spec),
    ),
    "repeat_each": lambda spec, context: repeat_each(
        context,
        spec_group(spec),
        spec.get("input"),
        spec_id(spec),
    ),
}


def action_from_recipe(spec: dict[str, Any], context: ActionContext | None = None) -> Action:
    kind = spec.get("kind")
    if not isinstance(kind, str):
        raise ValueError("Action is missing string field 'kind'")

    context = context or ActionContext()
    context_factory = CONTEXT_ACTION_FACTORIES.get(kind)
    if context_factory is not None:
        return context_factory(spec, context)

    factory = ACTION_FACTORIES.get(kind)
    if factory is None:
        supported = ", ".join(sorted(ACTION_FACTORIES | CONTEXT_ACTION_FACTORIES))
        raise ValueError(f"Unsupported action kind {kind!r}. Supported: {supported}")

    return factory(spec)
