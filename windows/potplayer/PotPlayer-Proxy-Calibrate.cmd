@echo off
rem One-time guided PotPlayer proxy calibration (for Socks-Proxy-On/Off with potPlayerProxy).
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Save-PotPlayer-ProxyProfile.ps1" -Step Wizard
pause
