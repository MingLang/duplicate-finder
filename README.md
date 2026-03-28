# Duplicate File Finder

A portable Windows desktop app to find and remove duplicate files. No installation required — just run the `.exe`.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![PySide6](https://img.shields.io/badge/GUI-PySide6-green) ![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey)

## Features

- Scan any folder or entire drive for duplicate files
- Three-stage detection: size pre-filter → partial hash → full SHA256, handles large drives efficiently
- Results show file name, duplicate count, wasted space, and full paths
- Check files and delete to Recycle Bin (recoverable) — never permanent deletion
- **Auto-Keep Newest / Oldest** — one click to select which duplicates to remove
- Right-click any file → "Keep this, delete others in group"
- Export results to CSV
- Drag-and-drop folders onto the scan list
- Progress indicator with cancel support
- Portable INI settings stored next to the `.exe`

## Usage

### Run from source

```bash
pip install -r requirements.txt
python src/main.py
```

### Build portable .exe

```bash
build.bat
```

Output: `dist\DuplicateFinder.exe` — copy anywhere and run, no installation needed.

## Requirements (for building)

- Python 3.10+
- Dependencies installed automatically by `build.bat`:
  - PySide6
  - send2trash
  - PyInstaller

## Project Structure

```
src/
  main.py                  # Entry point
  core/
    models.py              # Data classes: FileInfo, DuplicateGroup, ScanResult
    hasher.py              # MD5 / SHA256 file hashing
    scanner.py             # 3-stage duplicate detection pipeline
  gui/
    main_window.py         # Main application window
    scan_panel.py          # Left panel: path picker and options
    results_table.py       # Duplicate groups tree with checkboxes
    progress_dialog.py     # Scan progress dialog
  workers/
    scan_worker.py         # Background QThread for non-blocking scans
  utils/
    file_ops.py            # Safe delete via send2trash
    config.py              # Portable INI settings
    format.py              # Human-readable file sizes
resources/
  styles.qss               # Qt stylesheet
build.bat                  # One-command build script
build.spec                 # PyInstaller configuration
```
