@echo off
setlocal
pushd "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment missing. Run:
    echo   py -3.12 -m venv .venv
    popd
    exit /b 1
)
".venv\Scripts\python.exe" tools\build.py %*
set "BUILD_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %BUILD_EXIT_CODE%
