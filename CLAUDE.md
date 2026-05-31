# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A PySide6 GUI desktop app that batch-converts JPG/JPEG files to lossless WebP. Targeted at non-developers (photographers) who double-click an `.exe`. The app runs on all platforms but distributes as a Windows binary.

## Running the app

Python 3.10+ is required (`PySide6>=6.6.0` dropped Python 3.9 support).

```bash
# First-time setup
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the GUI
python app.py
```

## Building a distributable

```bash
# Linux / macOS
./build.sh

# Windows (cmd — double-click friendly)
build.bat

# Windows (PowerShell)
./build.ps1

# Or directly (after installing deps + pyinstaller)
python build.py
```

`build.py` runs PyInstaller in `--onedir --windowed --noupx` mode and zips the result to `dist/convert-to-webp2-<os>.zip`. The `build.sh/bat/ps1` scripts create `.venv`, install deps, then call `build.py`.

## Architecture

Two source files, intentionally decoupled:

- **`converter.py`** — pure conversion logic, no GUI dependency. Contains `find_jpeg_files`, `convert_file` (Pillow + piexif), `convert_one` (exception-safe wrapper returning `ConvertResult`), and `_patch_webp_exif` (post-save EXIF prefix fix for Windows WIC codec compatibility).
- **`app.py`** — PySide6 GUI. `Worker(QThread)` drives a `ThreadPoolExecutor` with up to `MAX_WORKERS=5` concurrent threads, emitting `progress`, `fileDone`, and `finishedAll` signals back to `MainWindow`.

### Threading model

- Conversion runs in `Worker` (a `QThread`) which internally uses `ThreadPoolExecutor`.
- libwebp encoding and LANCZOS resize release the GIL in C, so threads genuinely parallelize on multi-core machines.
- Cancellation sets a `threading.Event`; in-flight futures complete, pending futures are cancelled via `Future.cancel()`. This keeps disk state and counters consistent.
- All signal handlers in `MainWindow` run on the main (Qt) thread.

### EXIF handling quirk

After Pillow saves a WebP file, `_patch_webp_exif` rewrites the EXIF chunk to prepend `Exif\x00\x00` if missing. This is needed because Windows Explorer / WIC codec requires that prefix even though the WebP spec doesn't mandate it.

## Key constants / options

- `MAX_WORKERS = 5` in `app.py` — hard cap on concurrent conversions regardless of CPU count.
- WebP save flags: `lossless=True`, `quality=100`, `method=6` — these are fixed (no lossy mode).
- Output goes to `<selected_folder>/webp/`, filename is `<stem>.webp`.
- `find_jpeg_files` scans only the top-level directory (no recursion) and deduplicates by resolved path.

## Build artifacts

- `build/` and `dist/` are PyInstaller output — do not edit.
- `version.txt` is embedded as Windows file-properties metadata when building on Windows.
- `icon.ico` / `icon.icns` are picked up automatically by `build.py` if present.
