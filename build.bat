@echo off
echo ============================================
echo  Podcast Outreach Pro - Build .exe
echo ============================================
echo.

echo Checking dependencies...

python -c "import customtkinter, openai, selenium, undetected_chromedriver, PyInstaller" 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: Missing dependencies. Run install.bat first.
    echo.
    pause
    exit /b 1
)

echo Dependencies OK. Building...
echo.

pyinstaller --onefile --windowed --name "PodcastOutreachPro" --add-data "src;src" --hidden-import customtkinter --hidden-import undetected_chromedriver --hidden-import selenium --hidden-import openai --collect-all customtkinter main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed.
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
