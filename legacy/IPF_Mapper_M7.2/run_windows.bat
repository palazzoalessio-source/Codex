@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencies
py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if errorlevel 1 goto try_python
py -3 -m venv .venv
if errorlevel 1 goto failed
goto dependencies
:try_python
python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if errorlevel 1 (
  echo Installa Python 3.10 o successivo da python.org, poi riapri questo file.
  pause
  exit /b 1
)
python -m venv .venv
if errorlevel 1 goto failed
:dependencies
".venv\Scripts\python.exe" -c "import PySide6.QtWidgets" >nul 2>&1
if not errorlevel 1 goto launch
echo Installazione delle dipendenze di IPF Mapper...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
:launch
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Avvio non riuscito. Conserva il messaggio di errore visualizzato sopra.
pause
exit /b 1
