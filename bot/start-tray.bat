@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is niet gevonden. Installeer Python 3.10 of nieuwer en vink "Add python.exe to PATH" aan.
  pause
  exit /b 1
)

if not exist ".env" (
  echo Geen .env gevonden in deze map. Kopieer .env.example naar .env en vul die in.
  pause
  exit /b 1
)

set "NEEDINSTALL=0"
if not exist ".venv\Scripts\pythonw.exe" set "NEEDINSTALL=1"
if "%NEEDINSTALL%"=="0" (
  ".venv\Scripts\python.exe" -c "import customtkinter, pystray, PIL, discord, aiohttp" >nul 2>nul
  if errorlevel 1 set "NEEDINSTALL=1"
)
if "%NEEDINSTALL%"=="0" goto starten

echo Eerste keer: eigen Python-omgeving maken en onderdelen installeren. Dit duurt even...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto fout
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --prefer-binary -r requirements.txt > install.log 2>&1
if errorlevel 1 goto fout

:starten
rem Geen venster, geen terminal: de starter verschijnt in het systeemvak (naast de klok).
start "" ".venv\Scripts\pythonw.exe" "%~dp0tray.py"
exit /b 0

:fout
echo.
echo Installeren mislukt. De laatste regels van install.log:
if exist install.log powershell -NoProfile -Command "Get-Content install.log -Tail 15"
echo.
echo Stuur de regels hierboven door of probeer opnieuw. Python-versie:
python --version
pause
exit /b 1
