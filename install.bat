@echo off
echo ============================================
echo  Podcast Outreach Pro - Install Dependencies
echo ============================================
echo.

pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Installation failed. Make sure Python and pip are installed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  All dependencies installed successfully!
echo  Now run build.bat to create the .exe
echo ============================================
echo.
pause
