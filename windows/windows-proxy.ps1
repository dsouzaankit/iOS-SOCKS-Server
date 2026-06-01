# Toggle Windows user proxy for iOS-SOCKS-Server (PAC / automatic setup script).
#
# Updates WinINET registry values AND DefaultConnectionSettings (required for
# Settings -> Proxy -> "Use setup script" and most apps).
#
# Usage (from this folder):
#   .\windows-proxy.ps1 -Action Status
#   .\windows-proxy.ps1 -Action On
#   .\windows-proxy.ps1 -Action Off

param(
    [ValidateSet("On", "Off", "Status")]
    [string] $Action = "Status",
    [string] $PhoneIp = "",
    [int] $WpadPort = 0,
    [string] $PacUrl = "",
    [string] $BackupPath = (Join-Path $env:LOCALAPPDATA "iOS-SOCKS-Server-proxy-backup.json")
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\IOS-Socks-Windows.ps1"
. "$PSScriptRoot\WinInet-ProxySettings.ps1"

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

function Get-ProxyState {
    $regPath = Get-WinInetSettingsPath
    $p = Get-ItemProperty -Path $regPath
    [pscustomobject]@{
        ManualEnabled = [bool]$p.ProxyEnable
        ManualServer  = [string]$p.ProxyServer
        PacUrl        = [string]$p.AutoConfigURL
        AutoDetect    = [bool]$p.AutoDetect
        BackupFile    = $BackupPath
        BackupExists  = Test-Path -LiteralPath $BackupPath
    }
}

function Save-ProxyBackup {
    if (Test-Path -LiteralPath $BackupPath) { return }
    Get-WinInetProxyBackupData | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $BackupPath -Encoding UTF8
}

function Restore-ProxyBackup {
    if (-not (Test-Path -LiteralPath $BackupPath)) {
        Clear-WinInetPacProxy
        return
    }
    $backup = Get-Content -LiteralPath $BackupPath -Raw | ConvertFrom-Json
    Restore-WinInetProxyBackupData -Backup $backup
    Remove-Item -LiteralPath $BackupPath -Force
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
        Write-Host "Windows user proxy (WinINET):"
        Write-Host "  PAC (setup script): $($s.PacUrl)"
        Write-Host "  Manual enabled:   $($s.ManualEnabled)"
        if ($s.ManualServer) { Write-Host "  Manual server:    $($s.ManualServer)" }
        Write-Host "  Auto-detect:      $($s.AutoDetect)"
        if ($s.BackupExists) { Write-Host "  Backup (for Off): $($s.BackupFile)" }
        if (-not $s.PacUrl -and $s.ManualServer) {
            Write-Host ""
            Write-Host 'Note: Manual proxy is set but PAC is empty. Run -Action On for setup script mode.'
        }
    }
    "On" {
        $url = Resolve-PacUrl
        Save-ProxyBackup
        Set-WinInetPacProxy -PacUrl $url
        Refresh-InternetSettings
        Write-Host "PAC proxy ON: $url"
        Write-Host 'Check Settings -> Network and Internet -> Proxy -> Use setup script.'
        Write-Host "Keep Pythonista in the foreground on the phone while tethering."
    }
    "Off" {
        Restore-ProxyBackup
        Refresh-InternetSettings
        Write-Host "Proxy settings restored (or cleared if no backup)."
    }
}
