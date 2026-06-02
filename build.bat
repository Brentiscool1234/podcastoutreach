@echo off
echo ============================================
echo  Podcast Outreach Pro - Build .exe
echo ============================================
echo.

echo Building with PyInstaller...
pyinstaller --onefile --windowed --name "PodcastOutreachPro" --add-data "src;src" --hidden-import customtkinter --hidden-import undetected_chromedriver --hidden-import selenium --hidden-import openai --collect-all customtkinter main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Make sure pyinstaller is installed:
    echo   pip install pyinstaller
    pause
    exit /b 1
)

if exist "dist\PodcastOutreachPro.exe" (
    copy /Y "dist\PodcastOutreachPro.exe" "PodcastOutreachPro.exe"
    echo.
    echo ============================================
    echo  BUILD SUCCESSFUL!
    echo  File: PodcastOutreachPro.exe
    echo ============================================
) else (
    echo ERROR: .exe not found in dist\ folder.
)

echo.
pause
