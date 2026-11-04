@echo off
setlocal

if not exist .venv\Scripts\python.exe goto create_venv
goto install_deps

:create_venv
python -m venv .venv

:install_deps
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed

powershell -NoProfile -ExecutionPolicy Bypass -File start.ps1
goto end

:failed
echo.
echo Dependency installation failed. Check the error above and try again.

:end
pause
