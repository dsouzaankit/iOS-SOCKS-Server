#Requires -Version 5.1
<#
.SYNOPSIS
  Pin Socks-Proxy-On.cmd / Socks-Proxy-Off.cmd to the desktop (one-click daily pair).
#>
[CmdletBinding()]
param(
    [string] $Desktop = [Environment]::GetFolderPath('Desktop')
)

$ErrorActionPreference = 'Stop'
$WindowsDir = $PSScriptRoot
$Shell = New-Object -ComObject WScript.Shell

function New-DailyShortcut {
    param(
        [string] $Name,
        [string] $CmdName
    )
    $target = Join-Path $WindowsDir $CmdName
    if (-not (Test-Path -LiteralPath $target)) {
        throw "Missing: $target"
    }
    $lnk = Join-Path $Desktop "$Name.lnk"
    $sc = $Shell.CreateShortcut($lnk)
    $sc.TargetPath = $target
    $sc.WorkingDirectory = $WindowsDir
    $sc.Description = "iOS SOCKS proxy — $Name"
    $sc.Save()
    Write-Host "Created: $lnk"
}

New-DailyShortcut -Name 'Socks Proxy ON' -CmdName 'Socks-Proxy-On.cmd'
New-DailyShortcut -Name 'Socks Proxy OFF' -CmdName 'Socks-Proxy-Off.cmd'
Write-Host ''
Write-Host 'Run socks5.py on the iPhone, then double-click Socks Proxy ON.'
