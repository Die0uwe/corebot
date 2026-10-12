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

if not exist ".venv\Scripts\python.exe" (
  echo Eerste keer: eigen Python-omgeving maken. Dit duurt even...
  python -m venv .venv
  if errorlevel 1 goto venvfout
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto venvfout
)

".venv\Scripts\python.exe" bot.py
pause
exit /b 0

:venvfout
echo.
echo Installeren mislukt. De halve omgeving wordt verwijderd, start dit bestand opnieuw om het nog eens te proberen.
if exist ".venv" rmdir /s /q ".venv"
pause
exit /b 1
