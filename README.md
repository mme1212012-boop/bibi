# Bibi

Bibi is a Windows desktop helper for monitoring a BlueStacks window and solving
Water Sort puzzles. It only observes the emulator and displays suggested moves;
it does not click or control apps inside BlueStacks.

## Requirements

- Windows 10/11
- Python 3.10 or later
- Tesseract OCR installed and available on `PATH`

### Build a Windows installer

Install Python 3.10 or later and Inno Setup 6, then double-click
`build_setup.bat`. It packages the app and creates `dist\Bibi-Setup.exe`.
Tesseract OCR must also be installed on the target PC and available on `PATH`.

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

## Water Sort suggestions

Enter one tube per line, writing its contents from bottom to top with one letter
per color. Each color must occur exactly four times; use `-` for an empty tube.
Press **Tìm lời giải** to get suggested pours. The solver does not perform those
moves automatically.
