# Bibi

Bibi is a Windows desktop helper for monitoring a BlueStacks window and solving
Water Sort puzzles. It can optionally click the moves from a solution entered
by the user.

## Requirements

- Windows 10/11
- Python 3.10 or later
- Tesseract OCR installed and available on `PATH`

### Build a Windows installer

Install Python 3.10 or later and Inno Setup 6, then double-click
`build_setup.bat`. It packages the app and creates `dist\Bibi-Setup.exe`.
Tesseract OCR must also be installed on the target PC and available on `PATH`.

To download the latest published installer, use
[Bibi-Setup.exe](https://github.com/mme1212012-boop/bibi/releases/latest/download/Bibi-Setup.exe).

### Run from source

Install Python dependencies and start Bibi:

```powershell
py -m pip install -r requirements.txt
py bibi.py
```

## Monitor BlueStacks

1. Open BlueStacks and Widgetable.
2. In Bibi, refresh the window list and choose the BlueStacks window.
3. Optionally enter a crop rectangle relative to the window to focus OCR on the
   displayed coin/point count. A width or height of `0` uses the rest of that
   dimension.
4. Press **Bắt đầu** to capture the window every two seconds, or **Dừng** to stop.

Bibi reports the first number recognized in the selected region and its change
since the previous capture. OCR accuracy depends on the selected region,
emulator scaling, and Tesseract installation.

## Live Water Sort guidance

Press **Tự xem & chỉ dẫn** without selecting a window. Bibi opens fullscreen
and captures the primary screen about every 0.6 seconds, recognizes the board,
solves the current state, and highlights the next pour on the preview:

- a **red** ring marks the source tube;
- a **green** ring marks the destination tube;
- a yellow arrow and text show the color, amount, and tube numbers.

The guidance updates automatically after the board changes. Press **Dừng**
to stop live viewing. Live mode is guidance only and never clicks the game.

## Water Sort auto-recognition and auto-click

Open an active Water Sort level in BlueStacks and select its window in Bibi.
Press **Tự nhận diện & tính** to capture the board, detect tube positions and
sample the four color slots in each tube. Bibi only continues when the state
validates as a Water Sort puzzle (four slots per color and at least one empty
slot). It displays the detected state and proposed moves; confirm the prompt
before Bibi clicks. Immediately before clicking, Bibi captures the board again
and aborts if the detected state or tube positions changed.

Automatic detection expects the light blue/lavender board and outlined tube
mouths shown in the sample screenshots. Keep the active board visible and
unobstructed; Bibi does not navigate game menus or press in-game Start/Play
buttons. If detection fails, use the manual solver below.

Enter one tube per line, writing its contents from bottom to top with one letter
per color. Each color must occur exactly four times; use `-` for an empty tube.
Press **Tìm lời giải** to get suggested pours. To execute a manually entered
solution, enter the center coordinates of every tube, in row order from top to
bottom and left to right, relative to the selected BlueStacks window (for
example, `100,300; 180,300; 260,300; 340,300`), then press **Tự bấm lời giải**
and confirm. Use **Dừng tự bấm** to stop execution.

Coordinates must match the current window size and tube layout. The auto-click
feature uses PyAutoGUI's corner failsafe; moving the mouse to the screen's
top-left corner aborts clicking.

## Automatic updates

The packaged Windows app checks GitHub Releases at startup. When it finds a
newer release, it downloads `Bibi-Setup.exe`, verifies the SHA-256 digest
published by GitHub, runs the installer silently, and restarts Bibi. The
**Kiểm tra cập nhật** button can also be used to check manually.

To publish an update, set the same `x.y.z` version in `version.py` and
`installer.iss`, then push a matching `vX.Y.Z` tag. The Windows workflow builds
the installer and publishes it as a GitHub Release asset. Pushing to `main`
continues to build workflow artifacts but does not publish an update.
