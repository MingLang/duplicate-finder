@echo off
echo ============================================
echo  Duplicate File Finder - Build Script
echo ============================================
echo.

echo [1/2] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [2/2] Building portable executable...
python -m PyInstaller build.spec --noconfirm --workpath "%TEMP%\DupFinderBuild" --distpath dist
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Output: dist\DuplicateFinder.exe
echo  Copy DuplicateFinder.exe anywhere and run.
echo ============================================
pause
