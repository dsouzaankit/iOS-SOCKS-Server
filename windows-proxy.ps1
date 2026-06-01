# Toggle Windows user proxy for iOS-SOCKS-Server (PAC / automatic setup script).
#
# Matches Settings -> Network & Internet -> Proxy -> "Use setup script".
# Per-user only (HKCU); does not change WinHTTP (netsh) proxy.
#
# Usage:
#   .\windows-proxy.ps1 -Action Status
#   .\windows-proxy.ps1 -Action On  -PhoneIp 172.20.10.1
#   .\windows-proxy.ps1 -Action On  -PacUrl http://172.20.10.1:8088/wpad.dat
#   .\windows-proxy.ps1 -Action Off
#
# Run socks5.py on the phone first; use the PAC URL from its startup banner.

param(
    [ValidateSet("On", "Off", "Status")]
    [string] $Action = "Status",

    [string] $PhoneIp = "172.20.10.1",
    [int] $WpadPort = 8088,
    [string] $PacUrl = "",

    [string] $BackupPath = (Join-Path $env:LOCALAPPDATA "iOS-SOCKS-Server-proxy-backup.json")
)

$ErrorActionPreference = "Stop"
$RegPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
$RegKeys = @("ProxyEnable", "ProxyServer", "ProxyOverride", "AutoConfigURL")

function Get-ProxyState {
    $p = Get-ItemProperty -Path $RegPath
    [pscustomobject]@{
        ManualEnabled = [bool]$p.ProxyEnable
        ManualServer  = [string]$p.ProxyServer
        Bypass        = [string]$p.ProxyOverride
        PacUrl        = [string]$p.AutoConfigURL
        BackupFile    = $BackupPath
        BackupExists  = Test-Path -LiteralPath $BackupPath
    }
}

function Save-ProxyBackup {
    if (Test-Path -LiteralPath $BackupPath) {
        return
    }
    $p = Get-ItemProperty -Path $RegPath
    $backup = @{}
    foreach ($key in $RegKeys) {
        $backup[$key] = $p.$key
    }
    $backup | ConvertTo-Json | Set-Content -LiteralPath $BackupPath -Encoding UTF8
}

function Restore-ProxyBackup {
    if (-not (Test-Path -LiteralPath $BackupPath)) {
        Set-ItemProperty -Path $RegPath -Name ProxyEnable -Value 0 -Type DWord
        Remove-ItemProperty -Path $RegPath -Name AutoConfigURL -ErrorAction SilentlyContinue
        return
    }
    $backup = Get-Content -LiteralPath $BackupPath -Raw | ConvertFrom-Json
    foreach ($key in $RegKeys) {
        $val = $backup.$key
        if ($null -eq $val -or [string]::IsNullOrWhiteSpace([string]$val)) {
            Remove-ItemProperty -Path $RegPath -Name $key -ErrorAction SilentlyContinue
        } elseif ($key -eq "ProxyEnable") {
            Set-ItemProperty -Path $RegPath -Name $key -Value ([int]$val) -Type DWord
        } else {
            Set-ItemProperty -Path $RegPath -Name $key -Value ([string]$val)
        }
    }
    Remove-Item -LiteralPath $BackupPath -Force
}

function Refresh-InternetSettings {
    if (-not ("WinInet.Refresh" -as [type])) {
        $null = Add-Type -Namespace WinInet -Name Refresh -MemberDefinition @'
[DllImport("wininet.dll", SetLastError = true)]
public static extern bool InternetSetOption(System.IntPtr hInternet, int dwOption, System.IntPtr lpBuffer, int dwBufferLength);
'@
    }
    [WinInet.Refresh]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null
    [WinInet.Refresh]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null
}

function Resolve-PacUrl {
    if (-not [string]::IsNullOrWhiteSpace($PacUrl)) {
        return $PacUrl.Trim()
    }
    return "http://${PhoneIp}:${WpadPort}/wpad.dat"
}

switch ($Action) {
    "Status" {
        $s = Get-ProxyState
        Write-Host "Windows user proxy (current user):"
        Write-Host "  PAC (setup script): $($s.PacUrl)"
        Write-Host "  Manual enabled:   $($s.ManualEnabled)"
        if ($s.ManualServer) { Write-Host "  Manual server:    $($s.ManualServer)" }
        if ($s.BackupExists) { Write-Host "  Backup (for Off): $($s.BackupFile)" }
        break
    }
    "On" {
        $url = Resolve-PacUrl
        Save-ProxyBackup
        Set-ItemProperty -Path $RegPath -Name ProxyEnable -Value 0 -Type DWord
        Set-ItemProperty -Path $RegPath -Name AutoConfigURL -Value $url
        Refresh-InternetSettings
        Write-Host "PAC proxy ON: $url"
        Write-Host "Keep Pythonista in the foreground on the phone while tethering."
        break
    }
    "Off" {
        Restore-ProxyBackup
        Refresh-InternetSettings
        Write-Host "Proxy settings restored (or cleared if no backup)."
        break
    }
}
