@echo off
setlocal

cd /d "%~dp0"

echo J.League Player Stats (Windows launcher)
echo.

where uv > nul 2> nul
if not errorlevel 1 (
  echo Using uv: uv run main.py
  uv run main.py
  goto :finished
)

if exist ".venv\Scripts\python.exe" (
  echo Using venv: .venv\Scripts\python.exe
  ".venv\Scripts\python.exe" main.py
  goto :finished
)

where py > nul 2> nul
if errorlevel 1 (
  echo Neither uv nor Python was found.
  echo Please install uv (https://docs.astral.sh/uv/) or Python 3.12+ and try again.
  pause
  exit /b 1
)
py main.py

:finished
if errorlevel 1 (
  echo.
  echo An error occurred. Please check the messages above.
  pause
  exit /b 1
)

echo.
echo Done.
pause
