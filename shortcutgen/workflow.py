from __future__ import annotations

import plistlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def new_action_uuid() -> str:
    return str(uuid.uuid4()).upper()


def action_output_token(output_uuid: str, output_name: str) -> dict[str, Any]:
    return {
        "Value": {
            "attachmentsByRange": {
                "{0, 1}": {
                    "OutputName": output_name,
                    "OutputUUID": output_uuid,
                    "Type": "ActionOutput",
                }
            },
            "string": "\ufffc",
        },
        "WFSerializationType": "WFTextTokenString",
    }


@dataclass(frozen=True)
class OutputRef:
    action_id: str
    output_name: str | None = None


@dataclass(frozen=True)
class Action:
    identifier: str
    parameters: dict[str, Any] = field(default_factory=dict)
    recipe_id: str | None = None
    uuid: str = field(default_factory=new_action_uuid)
    output_name: str = "Output"

    def to_plist(
        self,
        previous_action: "Action | None" = None,
        actions_by_id: dict[str, "Action"] | None = None,
    ) -> dict[str, Any]:
        actions_by_id = actions_by_id or {}
        parameters = resolve_parameter(self.parameters, actions_by_id)
        parameters.setdefault("UUID", self.uuid)

        if self.identifier == "is.workflow.actions.showresult" and "Text" not in parameters:
            if previous_action is not None:
                parameters["Text"] = action_output_token(
                    previous_action.uuid,
                    previous_action.output_name,
                )

        return {
            "WFWorkflowActionIdentifier": self.identifier,
            "WFWorkflowActionParameters": parameters,
        }


def resolve_parameter(value: Any, actions_by_id: dict[str, Action]) -> Any:
    if isinstance(value, OutputRef):
        source = actions_by_id.get(value.action_id)
        if source is None:
            raise ValueError(f"Unknown action reference {value.action_id!r}")
        return action_output_token(
            source.uuid,
            value.output_name or source.output_name,
        )

    if isinstance(value, dict):
        return {key: resolve_parameter(child, actions_by_id) for key, child in value.items()}

    if isinstance(value, list):
        return [resolve_parameter(child, actions_by_id) for child in value]

    return value


@dataclass(frozen=True)
class Shortcut:
    name: str
    actions: list[Action]
    glyph_number: int = 59511
    start_color: int = 4282601983

    def to_plist(self) -> dict[str, Any]:
        actions_by_id = self.actions_by_id()
        actions = []
        previous_action = None
        for action in self.actions:
            actions.append(action.to_plist(previous_action, actions_by_id))
            previous_action = action

        return {
            "WFWorkflowActions": actions,
            "WFWorkflowClientVersion": "2700.0.4",
            "WFWorkflowHasOutputFallback": False,
            "WFWorkflowIcon": {
                "WFWorkflowIconGlyphNumber": self.glyph_number,
                "WFWorkflowIconStartColor": self.start_color,
            },
            "WFWorkflowImportQuestions": [],
            "WFWorkflowMinimumClientVersion": 900,
            "WFWorkflowMinimumClientVersionString": "900",
            "WFWorkflowName": self.name,
            "WFWorkflowOutputContentItemClasses": [],
            "WFWorkflowTypes": [],
        }

    def actions_by_id(self) -> dict[str, Action]:
        actions_by_id = {}
        for action in self.actions:
            if action.recipe_id is None:
                continue
            if action.recipe_id in actions_by_id:
                raise ValueError(f"Duplicate action id {action.recipe_id!r}")
            actions_by_id[action.recipe_id] = action
        return actions_by_id

    def write(self, path: Path) -> None:
        with path.open("wb") as handle:
            plistlib.dump(self.to_plist(), handle, fmt=plistlib.FMT_XML, sort_keys=False)
