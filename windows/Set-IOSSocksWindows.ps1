#Requires -Version 5.1
<#
.SYNOPSIS
  Create or update per-PC settings (ios-socks-windows.json).

.DESCRIPTION
  Portable across Windows PCs: phone IP, proxy ports, iCloud Downloads path for deploy.ps1.
  Copy ios-socks-windows.example.json to ios-socks-windows.json once per machine.

.EXAMPLE
  Copy-Item ios-socks-windows.example.json ios-socks-windows.json
  .\Set-IOSSocksWindows.ps1 -PhoneHost 10.0.100.10

.EXAMPLE
  .\Set-IOSSocksWindows.ps1 -Show
#>
[CmdletBinding()]
param(
    [string] $PhoneHost = '',
    [int] $WpadPort = 0,
    [int] $LanDebugPort = 0,
    [string] $ICloudDownloads = '',
    [switch] $Show,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\IOS-Socks-Windows.ps1"

if ($Show) {
    Show-IOSSocksWindowsDiagnostics
    exit 0
}

Initialize-IOSSocksWindowsConfig -Force:$Force
$settings = Get-IOSSocksWindowsSettings

if (-not [string]::IsNullOrWhiteSpace($PhoneHost)) {
    $settings.phoneLanHost = $PhoneHost.Trim()
}
if ($WpadPort -gt 0) {
    $settings.wpadPort = $WpadPort
}
if ($LanDebugPort -gt 0) {
    $settings.lanDebugPort = $LanDebugPort
}
if (-not [string]::IsNullOrWhiteSpace($ICloudDownloads)) {
    $settings.iCloudDownloads = Resolve-IOSSocksPath $ICloudDownloads
}

if ([string]::IsNullOrWhiteSpace([string]$settings.phoneLanHost)) {
    Write-Host 'Enter iPhone LAN IP (from Pythonista socks5.py banner, e.g. 172.20.10.1):'
    $entered = (Read-Host).Trim()
    if (-not [string]::IsNullOrWhiteSpace($entered)) {
        $settings.phoneLanHost = $entered
    }
}

if ([string]::IsNullOrWhiteSpace([string]$settings.iCloudDownloads)) {
    $defaultIcloud = Join-Path $env:USERPROFILE 'iCloudDrive\Downloads'
    if (Test-Path -LiteralPath $defaultIcloud) {
        Write-Host "iCloud Downloads for deploy.ps1 [$defaultIcloud]:"
        Write-Host 'Press Enter to use that path, or type another folder:'
        $entered = (Read-Host).Trim()
        if ([string]::IsNullOrWhiteSpace($entered)) {
            $settings.iCloudDownloads = $defaultIcloud
        } else {
            $settings.iCloudDownloads = Resolve-IOSSocksPath $entered
        }
    }
}

Save-IOSSocksWindowsSettings -Settings $settings
Write-Host ''
Show-IOSSocksWindowsDiagnostics
Write-Host ''
Write-Host 'Next: run socks5.py on the phone, then:'
Write-Host '  .\Socks-Proxy-On.cmd   (or .\windows-proxy.ps1 -Action On)'
Write-Host '  .\Socks-Proxy-Off.cmd'
