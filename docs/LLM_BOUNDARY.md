# LLM Boundary

The LLM must output Shorthand recipe JSON, not plist and not Cherri.

## Contract

The model receives:

- The user's natural-language request.
- The supported action-kind list.
- This recipe schema.
- Optional examples.

The model returns:

- One JSON object.
- No Markdown.
- No comments.
- No plist keys unless inside a `raw` action.

The compiler then:

1. Parses JSON.
2. Validates shape, required fields, refs, groups, and supported action kinds.
3. Emits `.shortcut` plist.
4. Signs with Apple's `shortcuts sign`.

Use the CLI boundary like this:

```bash
python3 -m shortcutgen prompt "Ask me for a note, then copy it" --output build/prompt.txt
python3 -m shortcutgen validate-response build/model_response.json
python3 -m shortcutgen compile-response build/model_response.json --output build/generated.shortcut --sign
```

## Recipe Rules

- `name` is required.
- `actions` is a non-empty array.
- Each action has a `kind`.
- Actions that need to be referenced later should include `id`.
- References use `{ "ref": "action_id" }`.
- References must point to an earlier action.
- Control-flow starts use `id`; middle/end markers use `group`.

## Unsupported Requests

If a request requires an unsupported action, the model should return:

```json
{
  "name": "Unsupported",
  "unsupported": true,
  "reason": "This requires an action Shorthand does not support yet.",
  "actions": [
    {
      "kind": "comment",
      "text": "Unsupported request: explain the missing action here."
    }
  ]
}
```

The product UI should render that as a clear limitation, not attempt to install
the placeholder shortcut.

`validate-response` accepts this as a recognized model response. `compile` and
`compile-response` reject it because unsupported responses are not installable
shortcuts.

## Example

```json
{
  "name": "Ask and Notify",
  "actions": [
    {
      "id": "answer",
      "kind": "ask_for_input",
      "prompt": "What should I remember?"
    },
    {
      "kind": "notification",
      "title": "Captured",
      "body": {
        "ref": "answer"
      }
    }
  ]
}
```
