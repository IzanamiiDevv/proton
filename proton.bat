@echo off
setlocal

where python >nul 2>&1
if %errorlevel%==0 (
    python "%~dp0core.py" %*
) else (
    py "%~dp0core.py" %*
)

endlocal