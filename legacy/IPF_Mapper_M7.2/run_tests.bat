@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Avvia prima run_windows.bat per preparare Python e le dipendenze.
  pause
  exit /b 1
)
set QT_QPA_PLATFORM=offscreen
".venv\Scripts\python.exe" verify_release.py
set result=%errorlevel%
echo Risultati in verification\tests.txt e verification\verification.json
pause
exit /b %result%
