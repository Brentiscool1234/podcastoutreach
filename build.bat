@echo off
echo ============================================
echo  Podcast Outreach Pro - Build Script
echo ============================================
echo.

echo [1/3] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [2/3] Building .exe with PyInstaller...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "PodcastOutreachPro" ^
    --add-data "src;src" ^
    --hidden-import customtkinter ^
    --hidden-import undetected_chromedriver ^
    --hidden-import selenium ^
    --hidden-import openai ^
    --collect-all customtkinter ^
    main.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Copying .exe to project root...
if exist "dist\PodcastOutreachPro.exe" (
    copy "dist\PodcastOutreachPro.exe" "PodcastOutreachPro.exe"
    echo.
    echo ============================================
    echo  BUILD SUCCESSFUL!
    echo  Run: PodcastOutreachPro.exe
    echo ============================================
) else (
    echo ERROR: .exe not found in dist folder.
)

echo.
pause
