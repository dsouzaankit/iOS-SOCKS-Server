# Toggle Windows user proxy for iOS-SOCKS-Server (PAC / automatic setup script).
#
# Phone IP and ports: ios-socks-windows.json (see Set-IOSSocksWindows.ps1).
#
# Usage (from this folder):
#   .\windows-proxy.ps1 -Action Status
#   .\windows-proxy.ps1 -Action On -OpenBrowser
#   .\windows-proxy.ps1 -Action Off
#
# Run socks5.py on the phone first; use the PAC URL from its startup banner.

param(
    [ValidateSet("On", "Off", "Status")]
    [string] $Action = "Status",
    [string] $PhoneIp = "",
    [int] $WpadPort = 0,
    [string] $PacUrl = "",
    [switch] $OpenBrowser,
    [string] $BackupPath = (Join-Path $env:LOCALAPPDATA "iOS-SOCKS-Server-proxy-backup.json")
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\IOS-Socks-Windows.ps1"

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
    if (Test-Path -LiteralPath $BackupPath) { return }
    $p = Get-ItemProperty -Path $RegPath
    $backup = @{}
    foreach ($key in $RegKeys) { $backup[$key] = $p.$key }
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
    Get-IOSSocksPacUrl -PhoneHost $PhoneIp -WpadPort $WpadPort -PacUrlOverride $PacUrl
}

switch ($Action) {
    "Status" {
        $s = Get-ProxyState
        Write-Host "Config: $(Get-IOSSocksWindowsConfigPath)"
        Write-Host "  phoneLanHost: $(Get-IOSSocksPhoneHost -Override $PhoneIp)"
        Write-Host "  expected PAC: $(Resolve-PacUrl)"
        Write-Host "Windows user proxy (current user):"
        Write-Host "  PAC (setup script): $($s.PacUrl)"
        Write-Host "  Manual enabled:   $($s.ManualEnabled)"
        if ($s.ManualServer) { Write-Host "  Manual server:    $($s.ManualServer)" }
        if ($s.BackupExists) { Write-Host "  Backup (for Off): $($s.BackupFile)" }
    }
    "On" {
        $url = Resolve-PacUrl
        Save-ProxyBackup
        Set-ItemProperty -Path $RegPath -Name ProxyEnable -Value 0 -Type DWord
        Set-ItemProperty -Path $RegPath -Name AutoConfigURL -Value $url
        Refresh-InternetSettings
        Write-Host "PAC proxy ON: $url"
        Write-Host "Keep Pythonista in the foreground on the phone while tethering."
        if ($OpenBrowser) {
            $debugUrl = Get-IOSSocksLanDebugUrl -PhoneHost $PhoneIp
            Write-Host "Opening $debugUrl"
            Start-Process $debugUrl
        }
    }
    "Off" {
        Restore-ProxyBackup
        Refresh-InternetSettings
        Write-Host "Proxy settings restored (or cleared if no backup)."
    }
}
