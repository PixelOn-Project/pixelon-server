@echo off
setlocal

echo ===============================================================================
echo  Pixelon All-in-One Build Script
echo ===============================================================================

if exist "venv\Scripts\activate.bat" (
    echo "[INFO] Activating virtual environment..."
    call venv\Scripts\activate.bat
) else (
    echo "[ERROR] Virtual environment (venv) not found!"
    goto :error
)

echo.
echo [STEP 1/5] Cleaning up previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"
if exist "build.zip" del /q "build.zip"

echo.
echo [STEP 2/5] Building Pixelon Server...
pyinstaller --noconsole --onedir --name "PixelOnServer" ^
    --collect-all "PIL" ^
    --collect-all "flask_cors" ^
    --collect-all "engineio" ^
    --collect-all "socketio" ^
    --collect-all "flask_socketio" ^
    --add-data "static;static" ^
    --icon "icon.ico" ^
    "app.py"

if %errorlevel% neq 0 (
    echo [ERROR] Server build failed.
    pause
    exit /b
)

echo.
echo [STEP 3/5] Building Pixelon Launcher...
pyinstaller --noconsole --onefile --name "PixelOnLauncher" ^
    --add-data "icon.ico;." ^
    --collect-all "customtkinter" ^
    --collect-all "pystray" ^
    --icon "icon.ico" ^
    "src/launcher.py"

if %errorlevel% neq 0 (
    echo [ERROR] Launcher build failed.
    pause
    exit /b
)

echo.
echo "[STEP 4/5] Packaging Server & Launcher into 'build.zip'..."

move "dist\PixelOnLauncher.exe" "dist\PixelOnServer\" >nul

powershell -Command "Compress-Archive -Path 'dist\PixelOnServer\*' -DestinationPath 'dist\build.zip' -Force"

if exist "dist\build.zip" (
    echo [OK] build.zip created successfully.
) else (
    echo [ERROR] Failed to create build.zip.
    pause
    exit /b
)

echo.
echo [STEP 5/5] Building Pixelon Installer...

pyinstaller --noconsole --onefile --uac-admin --name "PixelOnSetup" ^
    --collect-all "customtkinter" ^
    --hidden-import "winshell" ^
    --hidden-import "win32com" ^
    --hidden-import "hardware_scan" ^
    --paths "src" ^
    --icon "icon.ico" ^
    "src/installer.py"

if %errorlevel% neq 0 (
    echo [ERROR] Installer build failed.
    pause
    exit /b
)

echo.
echo ===============================================================================
echo  Build Complete!
echo ===============================================================================
echo.
echo [OUTPUT FILES]
echo 1. Installer:  dist\PixelonSetup.exe  (Distribute this to users)
echo 2. Server Core: dist\build.zip        (Upload this to GitHub Releases)
echo.
pause