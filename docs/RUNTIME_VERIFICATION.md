# Runtime Verification

Signer acceptance proves the file is structurally acceptable to Apple's signer.
It does not prove the shortcut imports, syncs, or runs correctly on iPhone.

## Build A Signed Fixture

```bash
mkdir -p build/runtime
python3 -m shortcutgen compile recipes/show_text.json --output build/runtime/show_text.shortcut --sign
```

The signed file is:

```text
build/runtime/show_text.signed.shortcut
```

## Import On Mac

The `shortcuts` CLI can list, view, run, and sign shortcuts, but it does not
expose an import subcommand. Import uses the Shortcuts app UI:

```bash
open build/runtime/show_text.signed.shortcut
```

After importing, verify the shortcut exists:

```bash
shortcuts list --show-identifiers | rg "Show Text"
```

Run it on Mac:

```bash
shortcuts run "Show Text"
```

## Verify On iPhone

1. Make sure iCloud Shortcuts sync is enabled on Mac and iPhone.
2. Import the signed shortcut on Mac.
3. Wait for it to appear in Shortcuts on iPhone.
4. Run it on iPhone.
5. Record whether each action renders with the expected title, parameters, and
   runtime behavior.

## Known Signer Noise

`shortcuts sign` may print repeated `debugDescription` attribute warnings while
still exiting successfully and producing a signed file. Treat the process exit
status and the existence of the signed file as the signer result.

## Current Manual Status

- Signed `recipes/show_text.json` fixture was generated at
  `build/runtime/show_text.signed.shortcut`.
- Opening the signed fixture reached the Shortcuts UI on Mac.
- `shortcuts list --show-identifiers` failed with
  `Couldn’t communicate with a helper application`.
- `shortcuts run "Show Text"` failed with
  `There was a problem running the shortcut`.
- Not yet verified on iPhone. This remains the next product gate before
  expanding the action catalog further.
