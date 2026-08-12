<img src="bachitouchbanner.png" alt="BachiTouch Banner" width="500">


BachiTouch is a web-based touchscreen drum controller for Taiko no Tatsujin and similar derivatives. It runs as a standalone Windows app that hosts a web-based controller that serves a mobile touchscreen drum UI from your PC, forwards taps over WebSocket, and simulates keyboard input for Taiko no Tatsujin or similar derivatives.

You don't need to download a separate app for your Android/iOS device to use this.

## ‼️DISCLAIMER
This app and it's contents are ENTIRELY MADE by using Github Copilot in VSC and Google Gemini as an exploration of automated code generation. By executing, installing, or interacting with this app, you acknowledge and agree that you do so entirely at your own discretion and risk. 

This project is complete and functional, but it is now provided "as-is." I am no longer actively developing or maintaining this repository. You are welcome to fork it if you want to make changes!

That being said I haven't found something like this after searching for years and figured playing around with Github Copilot and making this seems like a good opportunity. So if anyone sees this repo, **PLEASE MAKE SOMETHING LIKE THIS WITHOUT ALL THE VIBECODING STUFF!!!**

## What’s Included
- `BachiTouch.exe` — packaged desktop launcher and web server.
- Bundled Python runtime and dependencies.

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
- Tap outside the drum for rim hits (Katsu).
- Tap inside the drum for face hits (Don).
- Mobile View button is on the bottom-left for smaller screens.
- Press on help icon for more info.

## USB Mode (Android)
1. Enable USB debugging on the Android device.
2. Connect the device to the PC with USB.
3. Enable `Connect by USB` in the app and start the server.
4. Allow the device to authorize ADB access.
5. The app will use `adb reverse` so the phone can open `http://localhost:<port>/`.

## Notes
- The packaged version already includes required Python dependencies; no separate `pip install` step is required.
- If the game needs focus, make sure the Taiko window is active when tapping.
- Use the GUI to stop the server before closing the app.

## Troubleshooting
- If the mobile UI cannot connect, confirm the server is running and use the exact URL shown in the GUI.
- If USB mode fails, confirm ADB authorization on the device and that USB debugging is enabled.
- If game input is not detected, ensure the Taiko game window has focus on the PC.
