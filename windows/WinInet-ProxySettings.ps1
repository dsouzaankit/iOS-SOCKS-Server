#Requires -Version 5.1
# WinINET proxy via DefaultConnectionSettings (what Windows apps actually use).
# PAC-only blob format from https://www.spad.uk/posts/how-does-proxysettingsperuser-work/

function Get-WinInetConnectionsPath {
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings\Connections'
}

function Get-WinInetSettingsPath {
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
}

function New-PacConnectionSettingsBytes {
    param([string] $PacUrl)
    $revision = 2
    $proxyOptions = 5   # PAC only (no manual proxy, no auto-detect)
    $pacBytes = [System.Text.Encoding]::ASCII.GetBytes($PacUrl)
    $proxyBytes = [byte[]]@()
    $bypassBytes = [byte[]]@()
    [byte[]]@(
        @(70, 0, 0, 0) +
        @($revision, 0, 0, 0) +
        @($proxyOptions, 0, 0, 0) +
        @(0, 0, 0, 0) + $proxyBytes +
        @(0, 0, 0, 0) + $bypassBytes +
        @($pacBytes.Length, 0, 0, 0) + $pacBytes +
        @(1..32 | ForEach-Object { 0 })
    )
}

function New-DisabledConnectionSettingsBytes {
    $revision = 2
    $proxyOptions = 1   # nothing enabled
    $pacBytes = [byte[]]@()
    $proxyBytes = [byte[]]@()
    $bypassBytes = [byte[]]@()
    [byte[]]@(
        @(70, 0, 0, 0) +
        @($revision, 0, 0, 0) +
        @($proxyOptions, 0, 0, 0) +
        @(0, 0, 0, 0) + $proxyBytes +
        @(0, 0, 0, 0) + $bypassBytes +
        @(0, 0, 0, 0) + $pacBytes +
        @(1..32 | ForEach-Object { 0 })
    )
}

function New-ManualConnectionSettingsBytes {
    param(
        [string] $ProxyServer,
        [string] $Bypass = ''
    )
    $revision = 2
    $proxyOptions = 3   # manual proxy only
    $pacBytes = [byte[]]@()
    $proxyBytes = [System.Text.Encoding]::ASCII.GetBytes($ProxyServer)
    $bypassBytes = [System.Text.Encoding]::ASCII.GetBytes($Bypass)
    [byte[]]@(
        @(70, 0, 0, 0) +
        @($revision, 0, 0, 0) +
        @($proxyOptions, 0, 0, 0) +
        @($proxyBytes.Length, 0, 0, 0) + $proxyBytes +
        @($bypassBytes.Length, 0, 0, 0) + $bypassBytes +
        @(0, 0, 0, 0) + $pacBytes +
        @(1..32 | ForEach-Object { 0 })
    )
}

function Sync-WinInetBlobFromRegistry {
    $regPath = Get-WinInetSettingsPath
    $p = Get-ItemProperty -Path $regPath
    $pac = [string]$p.AutoConfigURL
    $server = [string]$p.ProxyServer
    $manual = [bool]$p.ProxyEnable
    if (-not [string]::IsNullOrWhiteSpace($pac)) {
        $bytes = New-PacConnectionSettingsBytes -PacUrl $pac.Trim()
    } elseif ($manual -and -not [string]::IsNullOrWhiteSpace($server)) {
        $bytes = New-ManualConnectionSettingsBytes -ProxyServer $server.Trim() -Bypass ([string]$p.ProxyOverride)
    } else {
        $bytes = New-DisabledConnectionSettingsBytes
    }
    Set-WinInetConnectionSettingsBytes -Bytes $bytes
}

function Set-WinInetConnectionSettingsBytes {
    param([byte[]] $Bytes)
    $connPath = Get-WinInetConnectionsPath
    Set-ItemProperty -Path $connPath -Name DefaultConnectionSettings -Value $Bytes
    Set-ItemProperty -Path $connPath -Name SavedLegacySettings -Value $Bytes
}

function Set-WinInetPacProxy {
    param([string] $PacUrl)
    $regPath = Get-WinInetSettingsPath
    Set-ItemProperty -Path $regPath -Name AutoDetect -Value 0 -Type DWord
    Set-ItemProperty -Path $regPath -Name ProxyEnable -Value 0 -Type DWord
    Set-ItemProperty -Path $regPath -Name AutoConfigURL -Value $PacUrl
    Remove-ItemProperty -Path $regPath -Name ProxyServer -ErrorAction SilentlyContinue
    $bytes = New-PacConnectionSettingsBytes -PacUrl $PacUrl
    Set-WinInetConnectionSettingsBytes -Bytes $bytes
}

function Clear-WinInetPacProxy {
    $regPath = Get-WinInetSettingsPath
    Set-ItemProperty -Path $regPath -Name AutoDetect -Value 0 -Type DWord
    Set-ItemProperty -Path $regPath -Name ProxyEnable -Value 0 -Type DWord
    Remove-ItemProperty -Path $regPath -Name AutoConfigURL -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path $regPath -Name ProxyServer -ErrorAction SilentlyContinue
    $bytes = New-DisabledConnectionSettingsBytes
    Set-WinInetConnectionSettingsBytes -Bytes $bytes
}

function Get-WinInetProxyBackupData {
    $regPath = Get-WinInetSettingsPath
    $connPath = Get-WinInetConnectionsPath
    $p = Get-ItemProperty -Path $regPath
    $conn = Get-ItemProperty -Path $connPath -ErrorAction SilentlyContinue
    $data = [ordered]@{
        ProxyEnable = $p.ProxyEnable
        ProxyServer = [string]$p.ProxyServer
        ProxyOverride = [string]$p.ProxyOverride
        AutoConfigURL = [string]$p.AutoConfigURL
        AutoDetect = $p.AutoDetect
    }
    if ($conn.DefaultConnectionSettings) {
        $data.DefaultConnectionSettings = [Convert]::ToBase64String(
            [byte[]]$conn.DefaultConnectionSettings
        )
    }
    if ($conn.SavedLegacySettings) {
        $data.SavedLegacySettings = [Convert]::ToBase64String(
            [byte[]]$conn.SavedLegacySettings
        )
    }
    return $data
}

function Restore-WinInetProxyBackupData {
    param($Backup)
    $regPath = Get-WinInetSettingsPath
    $connPath = Get-WinInetConnectionsPath
    foreach ($name in @('ProxyEnable', 'AutoDetect')) {
        if ($null -ne $Backup.$name) {
            Set-ItemProperty -Path $regPath -Name $name -Value ([int]$Backup.$name) -Type DWord
        }
    }
    foreach ($name in @('ProxyServer', 'ProxyOverride', 'AutoConfigURL')) {
        $val = [string]$Backup.$name
        if ([string]::IsNullOrWhiteSpace($val)) {
            Remove-ItemProperty -Path $regPath -Name $name -ErrorAction SilentlyContinue
        } else {
            Set-ItemProperty -Path $regPath -Name $name -Value $val
        }
    }
    if ($Backup.DefaultConnectionSettings) {
        $bytes = [Convert]::FromBase64String([string]$Backup.DefaultConnectionSettings)
        Set-ItemProperty -Path $connPath -Name DefaultConnectionSettings -Value $bytes
    }
    if ($Backup.SavedLegacySettings) {
        $bytes = [Convert]::FromBase64String([string]$Backup.SavedLegacySettings)
        Set-ItemProperty -Path $connPath -Name SavedLegacySettings -Value $bytes
    } elseif ($Backup.DefaultConnectionSettings) {
        $bytes = [Convert]::FromBase64String([string]$Backup.DefaultConnectionSettings)
        Set-ItemProperty -Path $connPath -Name SavedLegacySettings -Value $bytes
    }
    if (-not $Backup.DefaultConnectionSettings) {
        Sync-WinInetBlobFromRegistry
    }
}
