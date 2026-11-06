@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar-en-github.ps1"
echo.
if errorlevel 1 (
  echo No se ha completado la instalacion. Revisa el error indicado arriba.
) else (
  echo Instalacion finalizada. Revisa la web de GitHub y tu Telegram.
)
pause
