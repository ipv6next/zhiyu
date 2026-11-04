@echo off
setlocal

if not exist node_modules goto install_deps
goto start_web

:install_deps
npm install
if errorlevel 1 goto failed

:start_web
npm run dev -- --host 127.0.0.1
goto end

:failed
echo.
echo Dependency installation failed. Check the error above and try again.

:end
pause
