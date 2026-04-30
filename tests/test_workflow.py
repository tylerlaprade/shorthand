import json
import unittest

from shortcutgen.actions import (
    ActionContext,
    ask_for_input,
    dictionary,
    end_if,
    if_start,
    notification,
    show_result,
    text,
)
from shortcutgen.prompting import build_prompt, parse_model_response
from shortcutgen.system_intents import catalog_from_intentdefinition
from shortcutgen.validation import ValidationError, validate_recipe
from shortcutgen.workflow import Shortcut


class WorkflowTests(unittest.TestCase):
    def test_shortcut_plist_shape(self):
        shortcut = Shortcut(name="Example", actions=[text("Hello"), show_result()])
        plist = shortcut.to_plist()

        self.assertEqual(plist["WFWorkflowName"], "Example")
        self.assertEqual(
            plist["WFWorkflowActions"][0]["WFWorkflowActionIdentifier"],
            "is.workflow.actions.gettext",
        )
        self.assertEqual(
            plist["WFWorkflowActions"][0]["WFWorkflowActionParameters"]["WFTextActionText"],
            "Hello",
        )
        self.assertIn("UUID", plist["WFWorkflowActions"][0]["WFWorkflowActionParameters"])
        self.assertEqual(
            plist["WFWorkflowActions"][1]["WFWorkflowActionIdentifier"],
            "is.workflow.actions.showresult",
        )
        self.assertEqual(
            plist["WFWorkflowActions"][1]["WFWorkflowActionParameters"]["Text"][
                "WFSerializationType"
            ],
            "WFTextTokenString",
        )

    def test_explicit_action_reference(self):
        shortcut = Shortcut(
            name="Reference",
            actions=[
                ask_for_input("What should I remember?", recipe_id="answer"),
                notification("Captured", {"ref": "answer"}),
            ],
        )

        plist = shortcut.to_plist()
        answer_uuid = plist["WFWorkflowActions"][0]["WFWorkflowActionParameters"]["UUID"]
        body = plist["WFWorkflowActions"][1]["WFWorkflowActionParameters"][
            "WFNotificationActionBody"
        ]

        self.assertEqual(body["WFSerializationType"], "WFTextTokenString")
        self.assertEqual(
            body["Value"]["attachmentsByRange"]["{0, 1}"]["OutputUUID"],
            answer_uuid,
        )
        self.assertEqual(
            body["Value"]["attachmentsByRange"]["{0, 1}"]["OutputName"],
            "Provided Input",
        )

    def test_dictionary_action_shape(self):
        shortcut = Shortcut(
            name="Dictionary",
            actions=[dictionary({"source": "Shorthand"}, recipe_id="payload")],
        )

        wf_items = shortcut.to_plist()["WFWorkflowActions"][0]["WFWorkflowActionParameters"][
            "WFItems"
        ]

        self.assertEqual(wf_items["WFSerializationType"], "WFDictionaryFieldValue")
        self.assertEqual(
            wf_items["Value"]["WFDictionaryFieldValueItems"][0]["WFKey"],
            "source",
        )

    def test_control_flow_group_identifier_is_shared(self):
        context = ActionContext()
        shortcut = Shortcut(
            name="If",
            actions=[
                if_start(context, "condition", condition="Equals", recipe_id="condition"),
                end_if(context, "condition"),
            ],
        )

        actions = shortcut.to_plist()["WFWorkflowActions"]
        start = actions[0]["WFWorkflowActionParameters"]
        end = actions[1]["WFWorkflowActionParameters"]

        self.assertEqual(start["GroupingIdentifier"], end["GroupingIdentifier"])
        self.assertEqual(start["WFControlFlowMode"], 0)
        self.assertEqual(end["WFControlFlowMode"], 2)

    def test_validation_rejects_unknown_refs(self):
        with self.assertRaises(ValidationError):
            validate_recipe(
                {
                    "name": "Broken",
                    "actions": [
                        {
                            "kind": "show_result",
                            "text": {
                                "ref": "missing"
                            },
                        }
                    ],
                }
            )

    def test_validation_accepts_earlier_refs(self):
        validate_recipe(
            {
                "name": "Valid",
                "actions": [
                    {
                        "id": "answer",
                        "kind": "ask_for_input",
                        "prompt": "Question"
                    },
                    {
                        "kind": "show_result",
                        "text": {
                            "ref": "answer"
                        },
                    },
                ],
            }
        )

    def test_validation_rejects_unsupported_recipe_for_compilation(self):
        with self.assertRaises(ValidationError) as context:
            validate_recipe(
                {
                    "name": "Unsupported",
                    "unsupported": True,
                    "reason": "Needs a Photos action.",
                    "actions": [
                        {
                            "kind": "comment",
                            "text": "Unsupported request: Needs a Photos action."
                        }
                    ],
                }
            )

        self.assertIn("must not be compiled", str(context.exception))

    def test_model_response_accepts_unsupported_state(self):
        response = parse_model_response(
            json.dumps(
                {
                    "name": "Unsupported",
                    "unsupported": True,
                    "reason": "Needs a Photos action.",
                    "actions": [
                        {
                            "kind": "comment",
                            "text": "Unsupported request: Needs a Photos action."
                        }
                    ],
                }
            )
        )

        self.assertTrue(response.unsupported)
        self.assertEqual(response.reason, "Needs a Photos action.")

    def test_model_response_rejects_markdown(self):
        with self.assertRaisesRegex(ValueError, "no Markdown"):
            parse_model_response("```json\n{\"name\":\"Nope\"}\n```")

    def test_prompt_contains_request_and_supported_actions(self):
        prompt = build_prompt("Ask for a note and copy it to the clipboard")

        self.assertIn("Ask for a note and copy it to the clipboard", prompt)
        self.assertIn('"ask_for_input"', prompt)
        self.assertIn('"set_clipboard"', prompt)

    def test_system_intent_catalog_compacts_intentdefinition(self):
        catalog = catalog_from_intentdefinition(
            {
                "INIntentDefinitionNamespace": "example",
                "INEnums": [
                    {
                        "INEnumName": "BooleanSettingOperation",
                        "INEnumDisplayName": "Operation",
                        "INEnumValues": [
                            {
                                "INEnumValueName": "unknown",
                                "INEnumValueDisplayName": "unknown",
                            },
                            {
                                "INEnumValueName": "set",
                                "INEnumValueDisplayName": "Turn",
                                "INEnumValueIndex": 1,
                            },
                        ],
                    }
                ],
                "INIntents": [
                    {
                        "INIntentName": "SetWiFi",
                        "INIntentTitle": "Set Wi-Fi",
                        "INIntentDescription": "Sets Wi-Fi to on or off.",
                        "INIntentCategory": "set",
                        "INIntentVerb": "Set",
                        "INIntentParameters": [
                            {
                                "INIntentParameterName": "operation",
                                "INIntentParameterDisplayName": "Operation",
                                "INIntentParameterType": "Integer",
                                "INIntentParameterEnumType": "BooleanSettingOperation",
                                "INIntentParameterConfigurable": True,
                            }
                        ],
                    }
                ],
            }
        )

        self.assertEqual(catalog["intent_count"], 1)
        intent = catalog["intents"][0]
        self.assertEqual(intent["name"], "SetWiFi")
        self.assertEqual(intent["parameters"][0]["enum_values"][0]["name"], "set")


if __name__ == "__main__":
    unittest.main()
