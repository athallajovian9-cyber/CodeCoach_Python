@echo off
setlocal
cd /d "%~dp0"

REM  Watch a folder of Python and report, in plain words, what is wrong with it.
REM
REM  Drag a folder onto this file to watch that folder. Double-click it and it
REM  watches .\kidcode next to this file.

if not exist "codecoach.py" goto MISSING

where python >nul 2>&1
if %errorlevel% neq 0 goto NOPYTHON

set TARGET=%~1
if "%TARGET%"=="" set TARGET=%~dp0kidcode

if not exist "%TARGET%" (
    mkdir "%TARGET%" 2>nul
    echo.
    echo   Made a folder called kidcode. Put your kid's code on the folder and CodeCoach will instantly scan the code your kid makes.
    echo   Put the Python files in there and run this again.
    echo   Or drag any folder onto this file.
    echo.
    pause
    exit /b 0
)

echo.
echo   CodeCoach is watching:
echo     %TARGET%
echo.
echo   Save a file and this refreshes. Ctrl-C to stop.
echo.
python "codecoach.py" --watch --folder "%TARGET%"
pause
exit /b 0

:MISSING
echo.
echo   codecoach.py was not found next to this file.
echo   Keep the whole folder together.
echo.
pause
exit /b 1

:NOPYTHON
echo.
echo   Python was not found on PATH.
echo   Install Python 3 from python.org, then run this again.
echo.
pause
exit /b 1
