# Shorthand

Direct Shortcuts file generation experiments.

This repo currently contains a small, owned `.shortcut` generator. It emits
Apple Shortcuts workflow plists directly and can optionally sign them with the
macOS `shortcuts sign` command.

## Build A Sample

```bash
python3 -m shortcutgen compile recipes/show_text.json --output build/show_text.shortcut
shortcuts sign --mode anyone --input "$PWD/build/show_text.shortcut" --output "$PWD/build/show_text.signed.shortcut"
```

You can also ask the compiler to invoke the signer:

```bash
python3 -m shortcutgen compile recipes/show_text.json --output build/show_text.shortcut --sign
```

In restricted agent sandboxes, `shortcuts sign` may reject otherwise valid input.
Run the signing command from a normal terminal or from the app process itself.

## Model Boundary

Build a prompt for the LLM:

```bash
python3 -m shortcutgen prompt "Ask me for a note, then copy it" --output build/prompt.txt
```

Validate a raw model response:

```bash
python3 -m shortcutgen validate-response build/model_response.json
```

Compile only installable responses:

```bash
python3 -m shortcutgen compile-response build/model_response.json --output build/generated.shortcut --sign
```

Unsupported model responses are accepted by `validate-response` as UI states,
but `compile` and `compile-response` reject them.

## Recipe Shape

Recipes are JSON:

```json
{
  "name": "Show Text",
  "actions": [
    { "kind": "text", "text": "Hello from Shorthand" },
    { "kind": "show_result" }
  ]
}
```

Actions can have an `id`, and later actions can reference prior outputs:

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
      "body": { "ref": "answer" }
    }
  ]
}
```

For unsupported actions, use `raw`:

```json
{
  "kind": "raw",
  "identifier": "is.workflow.actions.comment",
  "parameters": {
    "WFCommentActionText": "Raw action escape hatch"
  }
}
```

## Supported Action Kinds

- `alert`
- `ask_for_input`
- `choose_from_menu`
- `comment`
- `current_date`
- `dictionary`
- `end_if`
- `end_menu`
- `end_repeat`
- `get_contents_of_url`
- `get_dictionary_from_input`
- `get_dictionary_value`
- `if`
- `menu_item`
- `notification`
- `open_url`
- `otherwise`
- `raw`
- `repeat_count`
- `repeat_each`
- `set_clipboard`
- `set_dictionary_value`
- `show_result`
- `text`
- `url`

See [docs/LLM_BOUNDARY.md](docs/LLM_BOUNDARY.md) and
[docs/recipe.schema.json](docs/recipe.schema.json) for the model-facing recipe
contract.

Apple WorkflowKit system intent metadata can be extracted with:

```bash
python3 -m shortcutgen system-intents --output build/system_intents.json
```

See [docs/SYSTEM_INTENTS.md](docs/SYSTEM_INTENTS.md).

Runtime import and iPhone sync checks are tracked in
[docs/RUNTIME_VERIFICATION.md](docs/RUNTIME_VERIFICATION.md).

## Mac App Shell

The SwiftUI shell can be run from the repository root:

```bash
swift run ShorthandApp
```

It currently wraps the local compiler flow: Claude-backed recipe generation,
response validation, signed shortcut compilation, and opening the signed file
for import. See [docs/MAC_APP.md](docs/MAC_APP.md).

Build an ad-hoc signed `.app` bundle:

```bash
scripts/build_app_bundle.sh
```
