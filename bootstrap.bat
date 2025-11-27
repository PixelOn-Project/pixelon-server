@echo off
setlocal

where grunt >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] 'grunt-cli' is missing in system PATH.
    set /p install_choice="[ACTION] Proceed with global installation? [y/N]: "
    
    if /i "%install_choice%"=="y" (
        call npm install -g grunt-cli
        set BUILD_CMD=grunt
    ) else (
        set BUILD_CMD=npx grunt
    )
) else (
    set BUILD_CMD=grunt
)

git submodule update --init --recursive

cd piskel
git pull origin dev
git checkout dev
call npm instal
call %BUILD_CMD% build

cd ../
if not exist "static\editor" mkdir "static\editor"
xcopy /E /Y /I "piskel\dest\*" "static\editor\"

call python -m venv venv
call ./venv/Scripts/activate
call pip install -r requirements.txt
call python fetch_binaries.py