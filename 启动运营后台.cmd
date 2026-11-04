@echo off
setlocal
set "PROJECT_ROOT=%~dp0"

echo Starting Zhiyu admin API...
start "Zhiyu Admin API" /D "%PROJECT_ROOT%admin-api" cmd /k call run-api.cmd

echo Starting Zhiyu admin web...
start "Zhiyu Admin Web" /D "%PROJECT_ROOT%admin-web" cmd /k call run-web.cmd

echo.
echo Open http://127.0.0.1:5190/ after both windows are ready.
echo Do not close the two service windows while testing.
pause
