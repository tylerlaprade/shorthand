# Shorthand Implementation Plan

## Goal

Build a product-owned Shortcuts generation core that accepts a constrained JSON
recipe, validates it, emits a `.shortcut` plist, and signs it with Apple's
`shortcuts sign` command.

## Status

- [x] Write repo plan and status tracker.
- [x] Add recipe validation layer.
- [x] Add control-flow actions.
- [x] Add HTTP and JSON/dictionary primitives.
- [x] Add LLM recipe boundary docs/schema.
- [x] Verify compile/sign fixtures.
- [x] Make unsupported model responses non-compilable.
- [x] Add prompt assembly for recipe generation.
- [x] Add model-response validation CLI.
- [x] Add runtime import/run verification notes.
- [x] Build native Mac app shell.
- [x] Add Claude API client and Keychain-backed settings.
- [x] Remove repo-root launch assumption from the Mac shell.
- [x] Package a real `.app` bundle.
- [x] Bundle compiler resources into packaged app.
- [x] Extract Apple WorkflowKit system intent metadata.
- [ ] Manually import and run signed fixtures on iPhone.

## Notes

- The compiler should own plist generation directly; do not depend on Cherri or
  other GPL tooling.
- LLMs should output recipe JSON only. They should never output raw plist.
- Signer acceptance is necessary but not sufficient. Runtime import/run testing
  on iPhone remains a separate manual verification step.
- Unsupported model responses are product UI states, not shortcuts to install.
