# BachiTouch

BachiTouch is a packaged Taiko remote controller for Windows. It runs as a standalone app that serves a mobile touchscreen drum UI from your PC, forwards taps over WebSocket, and simulates keyboard input for Taiko no Tatsujin or similar rhythm games.

## What’s Included
- `BachiTouch.exe` — packaged desktop launcher and web server.
- bundled Python runtime and dependencies.
- `static/` — mobile client UI, styles, icons, service worker, and assets.
- optional `adb/` folder for Android USB reverse support.

## Highlights
- Touch-optimized drum interface with left/right rim and face hit zones.
- Custom key mappings for all drum controls.
- Drum scale and touch zone opacity adjustments.
- Built-in WebSocket ping status and reconnect behavior.
- Optional Android USB mode via bundled ADB support.
- Offline-capable mobile UI with service worker caching.

## Getting Started
1. Extract the packaged release to a folder on your PC.
2. Run `BachiTouch.exe`.
3. In the GUI, choose the host IP and port to run the server.
4. Open the mobile URL shown in the GUI on your phone or tablet browser.
5. Configure drum key mappings on the phone.
6. Tap the drum zones to send input to the PC game.

## Mobile Usage
- Tap the outer drum area for rim hits (Katsu).
- Tap the inner drum area for face hits (Don).
- Use the quick overlay buttons for rapid input.
- Press the pause button to send a pause/escape signal to the game.
- The UI automatically shows connection status and ping latency.

## USB Mode (Android)
1. Enable USB debugging on the Android device.
2. Connect the device to the PC with USB.
3. Enable `Connect by USB` in the app.
4. Allow the device to authorize ADB access.
5. The app will use `adb reverse` so the phone can open `http://localhost:<port>/`.

## Notes
- The packaged version already includes required Python dependencies; no separate `pip install` step is required.
- If the game needs focus, make sure the Taiko window is active when tapping.
- Use the GUI to stop the server before closing the app.

## Included Files
- `BachiTouch.exe` — packaged application executable.
- `static/` — client assets and service worker files.
- `adb/` — optional Android ADB helper binaries.
- `README.md` — documentation.

## Troubleshooting
- If the mobile UI cannot connect, confirm the server is running and use the exact URL shown in the GUI.
- If USB mode fails, confirm ADB authorization on the device and that USB debugging is enabled.
- If game input is not detected, ensure the Taiko game window has focus on the PC.
