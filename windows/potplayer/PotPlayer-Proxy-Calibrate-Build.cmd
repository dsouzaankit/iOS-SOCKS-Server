@echo off
rem Build proxy patches from OFF/ON snapshots (run Off and On steps first).
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Save-PotPlayer-ProxyProfile.ps1" -Step Build
pause
