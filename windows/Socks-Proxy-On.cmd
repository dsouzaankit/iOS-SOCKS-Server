@echo off
rem One-click daily: PAC proxy ON (ios-socks-windows.json). Run socks5.py on iPhone first.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows-proxy.ps1" -Action On
if errorlevel 1 (
    pause
) else (
    timeout /t 3 /nobreak >nul
)
