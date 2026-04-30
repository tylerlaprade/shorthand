#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Shorthand"
BUNDLE_ID="com.tylerlaprade.shorthand"
CONFIGURATION="${CONFIGURATION:-release}"
EXECUTABLE_NAME="ShorthandApp"
APP_DIR="$ROOT_DIR/build/$APP_NAME.app"
EXECUTABLE_PATH="$ROOT_DIR/.build/$CONFIGURATION/$EXECUTABLE_NAME"

swift build -c "$CONFIGURATION" --package-path "$ROOT_DIR"

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

cp "$EXECUTABLE_PATH" "$APP_DIR/Contents/MacOS/$APP_NAME"
cp -R "$ROOT_DIR/shortcutgen" "$APP_DIR/Contents/Resources/shortcutgen"
cp -R "$ROOT_DIR/recipes" "$APP_DIR/Contents/Resources/recipes"
find "$APP_DIR/Contents/Resources" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$APP_DIR/Contents/Resources" -name "*.pyc" -type f -delete

cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>14.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

codesign --force --sign - "$APP_DIR"

echo "Built $APP_DIR"
