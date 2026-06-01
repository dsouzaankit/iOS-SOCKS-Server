@echo off
rem Snapshot PotPlayer registry with proxy ON (close PotPlayer first).
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Save-PotPlayer-ProxyProfile.ps1" -Step On
pause
