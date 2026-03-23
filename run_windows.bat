@echo off
setlocal

cd /d "%~dp0"

echo J.League Player Stats (Windows launcher)
echo.

if exist "venv\Scripts\python.exe" (
  echo Using venv: venv\Scripts\python.exe
  "venv\Scripts\python.exe" main.py
) else (
  where py > nul 2> nul
  if errorlevel 1 (
    echo Python launcher "py" was not found.
    echo Please install Python 3.12+ and try again.
    pause
    exit /b 1
  )
  py main.py
)

if errorlevel 1 (
  echo.
  echo An error occurred. Please check the messages above.
  pause
  exit /b 1
)

echo.
echo Done.
pause
