# System Intent Metadata

Apple ships readable Shortcuts intent metadata here:

```text
/System/Library/PrivateFrameworks/WorkflowKit.framework/PlugIns/ShortcutsIntents.appex/Contents/Resources/Base.lproj/Actions.intentdefinition
```

Extract it with:

```bash
python3 -m shortcutgen system-intents --output build/system_intents.json
```

This metadata is useful prompt/catalog context. It is not the same thing as
validated `.shortcut` plist serialization support. The compiler should not emit
these intents until each one has a verified action encoding and runtime fixture.

## Current Extracted Scope

On this machine, the WorkflowKit `Actions.intentdefinition` file exposes 25
intents:

- `AskForInput` — Ask for Input
- `ChangeCase` — Change Case
- `ChooseFromList` — Choose from List
- `CombineText` — Combine Text
- `CorrectSpelling` — Correct Spelling
- `DeletePhotos` — Delete Photos
- `MatchText` — Match Text
- `MatchTextGetGroup` — Get Group from Matched Text
- `SetAirplaneMode` — Set Airplane Mode
- `SetAlwaysOnDisplay` — Set Always On Display
- `SetAnnounceNotifications` — Set Announce Notifications
- `SetAppearance` — Set Appearance
- `SetBluetooth` — Set Bluetooth
- `SetBrightness` — Set Brightness
- `SetCellularData` — Set Cellular Data
- `SetFlashlight` — Set Flashlight
- `SetLowPowerMode` — Set Low Power Mode
- `SetNightShift` — Set Night Shift
- `SetOrientationLock` — Set Orientation Lock
- `SetPersonalHotspot` — Set Personal Hotspot
- `SetSilenceUnknownCallers` — Set Silence Unknown Callers
- `SetStageManager` — Set Stage Manager
- `SetTrueTone` — Set True Tone
- `SetWiFi` — Set Wi-Fi
- `SplitText` — Split Text

## Local Library Access

`~/Library/Shortcuts/Shortcuts.sqlite` is protected by macOS privacy controls on
this machine. Attempts to read it from this agent failed with
`authorization denied`, even outside the workspace sandbox. Use the system
intent metadata above unless Full Disk Access is explicitly granted for deeper
local shortcut mining.
