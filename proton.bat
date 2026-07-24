@echo off
setlocal

where python >nul 2>&1
if %errorlevel%==0 (
    python "%~dp0app.py" %*
) else (
    py "%~dp0app.py" %*
)

endlocal