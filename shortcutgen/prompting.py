from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .validation import SUPPORTED_KINDS, validate_recipe


ACTION_SPECS: dict[str, dict[str, Any]] = {
    "alert": {
        "description": "Show an alert with a title and optional message.",
        "required": ["title"],
        "optional": ["message", "show_cancel", "id"],
    },
    "ask_for_input": {
        "description": "Ask the user for text or another basic input type.",
        "required": ["prompt"],
        "optional": ["input_type", "id"],
    },
    "choose_from_menu": {
        "description": "Start a menu branch.",
        "required": ["id", "items"],
        "optional": ["prompt"],
    },
    "comment": {
        "description": "Add a non-running comment action.",
        "required": ["text"],
        "optional": ["id"],
    },
    "current_date": {
        "description": "Get the current date.",
        "required": [],
        "optional": ["id"],
    },
    "dictionary": {
        "description": "Create a dictionary from key-value items.",
        "required": ["items"],
        "optional": ["id"],
    },
    "end_if": {
        "description": "End an if block.",
        "required": ["group"],
        "optional": [],
    },
    "end_menu": {
        "description": "End a choose-from-menu block.",
        "required": ["group"],
        "optional": [],
    },
    "end_repeat": {
        "description": "End a repeat block.",
        "required": ["group"],
        "optional": [],
    },
    "get_contents_of_url": {
        "description": "Fetch a URL with an HTTP method and optional headers.",
        "required": [],
        "optional": ["url", "method", "headers", "id"],
    },
    "get_dictionary_from_input": {
        "description": "Parse input as a dictionary, useful for JSON responses.",
        "required": [],
        "optional": ["input", "id"],
    },
    "get_dictionary_value": {
        "description": "Read one key, all keys, or all values from a dictionary.",
        "required": ["key"],
        "optional": ["input", "get", "id"],
    },
    "if": {
        "description": "Start an if block.",
        "required": ["id"],
        "optional": ["input", "condition", "value"],
    },
    "menu_item": {
        "description": "Start one branch within a choose-from-menu block.",
        "required": ["group", "title"],
        "optional": [],
    },
    "notification": {
        "description": "Show a notification with a title and optional body.",
        "required": ["title"],
        "optional": ["body", "id"],
    },
    "open_url": {
        "description": "Open the previous URL action output or URL input.",
        "required": [],
        "optional": ["id"],
    },
    "otherwise": {
        "description": "Start the else branch for an if block.",
        "required": ["group"],
        "optional": [],
    },
    "raw": {
        "description": "Escape hatch for a known Shortcuts action identifier.",
        "required": ["identifier"],
        "optional": ["parameters", "id"],
    },
    "repeat_count": {
        "description": "Start a fixed-count repeat block.",
        "required": ["id", "count"],
        "optional": [],
    },
    "repeat_each": {
        "description": "Start a repeat-each block over input items.",
        "required": ["id"],
        "optional": ["input"],
    },
    "set_clipboard": {
        "description": "Set the clipboard to explicit input or previous action output.",
        "required": [],
        "optional": ["input", "id"],
    },
    "set_dictionary_value": {
        "description": "Set a dictionary key to a value.",
        "required": ["key", "value"],
        "optional": ["input", "id"],
    },
    "show_result": {
        "description": "Show explicit text or the previous action output.",
        "required": [],
        "optional": ["text", "id"],
    },
    "text": {
        "description": "Create a text value.",
        "required": ["text"],
        "optional": ["id"],
    },
    "url": {
        "description": "Create a URL value.",
        "required": ["url"],
        "optional": ["id"],
    },
}


@dataclass(frozen=True)
class ModelResponse:
    recipe: dict[str, Any]
    unsupported: bool = False
    reason: str | None = None


def action_catalog() -> dict[str, Any]:
    missing_specs = sorted(SUPPORTED_KINDS - frozenset(ACTION_SPECS))
    if missing_specs:
        raise ValueError(f"Missing prompt specs for action kinds: {', '.join(missing_specs)}")
    return {kind: ACTION_SPECS[kind] for kind in sorted(SUPPORTED_KINDS)}


def recipe_contract() -> dict[str, Any]:
    return {
        "output": "Return exactly one JSON object and no Markdown.",
        "recipe": {
            "name": "Required non-empty string.",
            "actions": "Required non-empty array of supported actions.",
        },
        "references": {
            "shape": {"ref": "earlier_action_id"},
            "rule": "References must point to an earlier action id.",
        },
        "control_flow": {
            "rule": "Start actions use id. Middle and end actions use group with the start id.",
        },
        "unsupported_response": {
            "name": "Unsupported",
            "unsupported": True,
            "reason": "Explain the missing capability.",
            "actions": [
                {
                    "kind": "comment",
                    "text": "Unsupported request: explain the missing action here.",
                }
            ],
        },
        "supported_actions": action_catalog(),
    }


def build_prompt(user_request: str, examples: list[dict[str, Any]] | None = None) -> str:
    request = user_request.strip()
    if not request:
        raise ValueError("User request must be a non-empty string")

    sections = [
        "You convert natural-language automation requests into Shorthand recipe JSON.",
        "Return exactly one JSON object. Do not return Markdown, comments, plist, or Cherri.",
        "If the request cannot be represented with supported actions, return the unsupported response shape.",
        "",
        "Recipe contract:",
        json.dumps(recipe_contract(), indent=2, sort_keys=True),
    ]

    if examples:
        sections.extend(
            [
                "",
                "Examples:",
                json.dumps(examples, indent=2, sort_keys=True),
            ]
        )

    sections.extend(
        [
            "",
            "User request:",
            request,
        ]
    )
    return "\n".join(sections)


def parse_model_response(raw_response: str) -> ModelResponse:
    response = raw_response.strip()
    if not response:
        raise ValueError("Model response is empty")

    try:
        recipe = json.loads(response)
    except json.JSONDecodeError as error:
        raise ValueError("Model response must be exactly one JSON object with no Markdown") from error

    if not isinstance(recipe, dict):
        raise ValueError("Model response must be a JSON object")

    if recipe.get("unsupported") is True:
        reason = recipe.get("reason")
        if not isinstance(reason, str) or not reason:
            raise ValueError("Unsupported model response must include non-empty string field 'reason'")
        return ModelResponse(recipe=recipe, unsupported=True, reason=reason)

    validate_recipe(recipe)
    return ModelResponse(recipe=recipe)
