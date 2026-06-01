@echo off
rem One-click daily: PAC proxy OFF (restores previous Windows proxy settings).
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows-proxy.ps1" -Action Off
if errorlevel 1 (
    pause
) else (
    timeout /t 3 /nobreak >nul
)
