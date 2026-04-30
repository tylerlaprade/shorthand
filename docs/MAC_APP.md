# Mac App Shell

The current Mac shell is a SwiftUI executable target built with SwiftPM. It
keeps the Python compiler as the source of truth and calls `python3 -m
shortcutgen` for prompt generation, validation, compilation, and signing.

## Run

Run in development:

```bash
swift run ShorthandApp
```

The app locates the compiler by checking `SHORTHAND_REPO_ROOT`, bundled
resources, walking upward from the launch directory and bundle path, then
falling back to `~/Code/shorthand`.

## Package

Build an ad-hoc signed app bundle:

```bash
scripts/build_app_bundle.sh
```

Output:

```text
build/Shorthand.app
```

The bundle includes `shortcutgen/` and `recipes/` in
`Contents/Resources/`. Generated prompts, model responses, and shortcut files
are written under:

```text
~/Library/Application Support/Shorthand/build/app/
```

## Current UI

- Request editor
- Recipe JSON editor
- Parsed action preview
- Generate button: calls Claude when an API key is saved, otherwise builds the
  LLM prompt and copies it to the clipboard
- Validate button: validates the recipe/model response
- Compile button: compiles and signs `build/app/generated.signed.shortcut`
- Install button: opens the signed shortcut with Shortcuts

## Claude Integration

- API key is stored in Keychain under the app service name.
- Model selection is stored in user defaults.
- Default model: `claude-sonnet-4-6`.
- API shape is Anthropic Messages API: `POST /v1/messages` with `x-api-key`,
  `anthropic-version: 2023-06-01`, JSON request body, and text response blocks.
- Reference docs checked on 2026-04-29:
  https://platform.claude.com/docs/en/build-with-claude/working-with-messages
  and https://platform.claude.com/docs/en/about-claude/models/overview

## Current Constraints

- The packaged app still depends on `/usr/bin/python3`.
- Mac import uses Shortcuts UI because the `shortcuts` CLI has no import
  subcommand.
