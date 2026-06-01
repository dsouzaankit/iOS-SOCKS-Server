#Requires -Version 5.1
# Shared per-PC settings for windows/*.ps1 (dot-source from $PSScriptRoot).

function Get-IOSSocksWindowsConfigPath {
    Join-Path $PSScriptRoot 'ios-socks-windows.json'
}

function Get-IOSSocksWindowsExamplePath {
    Join-Path $PSScriptRoot 'ios-socks-windows.example.json'
}

function Get-DefaultIOSSocksWindowsSettings {
    [ordered]@{
        phoneLanHost     = ''
        wpadPort         = 8088
        socksPort        = 9876
        httpPort         = 9877
        lanDebugPort     = 8765
        iCloudDownloads  = ''
        potPlayerProxy   = $false
        potPlayerRegKey  = 'PotPlayerMini64'
        notes            = ''
    }
}

function Read-IOSSocksWindowsConfigFile {
    param([string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
        if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
        return $raw | ConvertFrom-Json
    } catch {
        Write-Warning "Could not parse $Path : $($_.Exception.Message)"
        return $null
    }
}

function Merge-IOSSocksWindowsSettings {
    param($FromFile)
    $merged = Get-DefaultIOSSocksWindowsSettings
    if ($null -eq $FromFile) { return $merged }
    foreach ($prop in $FromFile.PSObject.Properties) {
        if ($merged.Contains($prop.Name)) {
            $merged[$prop.Name] = $prop.Value
        }
    }
    return $merged
}

function Import-IOSSocksLegacyPhoneHost {
    param([hashtable] $Settings)
    $legacy = Join-Path $PSScriptRoot 'ios-socks-phone-ip.txt'
    if (-not [string]::IsNullOrWhiteSpace([string]$Settings.phoneLanHost)) { return $Settings }
    if (-not (Test-Path -LiteralPath $legacy)) { return $Settings }
    $ip = (Get-Content -LiteralPath $legacy -Raw).Trim().Trim('"')
    if (-not [string]::IsNullOrWhiteSpace($ip)) {
        $Settings.phoneLanHost = $ip
    }
    return $Settings
}

function Get-IOSSocksWindowsSettings {
    $path = Get-IOSSocksWindowsConfigPath
    $fromFile = Read-IOSSocksWindowsConfigFile -Path $path
    $settings = Merge-IOSSocksWindowsSettings -FromFile $fromFile
    Import-IOSSocksLegacyPhoneHost -Settings $settings
}

function Save-IOSSocksWindowsSettings {
    param([hashtable] $Settings)
    $path = Get-IOSSocksWindowsConfigPath
    $ordered = [ordered]@{}
    foreach ($key in (Get-DefaultIOSSocksWindowsSettings).Keys) {
        $ordered[$key] = $Settings[$key]
    }
    $json = $ordered | ConvertTo-Json -Depth 4
    Set-Content -LiteralPath $path -Value $json -Encoding UTF8
    Write-Host "Saved: $path"
    $legacy = Join-Path $PSScriptRoot 'ios-socks-phone-ip.txt'
    if (-not [string]::IsNullOrWhiteSpace([string]$Settings.phoneLanHost)) {
        [string]$Settings.phoneLanHost.Trim() | Set-Content -LiteralPath $legacy -Encoding UTF8 -NoNewline
    }
}

function Initialize-IOSSocksWindowsConfig {
    param([switch] $Force)
    $path = Get-IOSSocksWindowsConfigPath
    if ((Test-Path -LiteralPath $path) -and -not $Force) { return }
    $example = Get-IOSSocksWindowsExamplePath
    if (-not (Test-Path -LiteralPath $example)) {
        throw "Missing example config: $example"
    }
    Copy-Item -LiteralPath $example -Destination $path -Force
    Write-Host "Created: $path (edit phoneLanHost for this PC)"
}

function Resolve-IOSSocksPath {
    param([string] $Path)
    $t = $Path.Trim().Trim('"')
    if ([string]::IsNullOrWhiteSpace($t)) { return '' }
    return [System.IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables(
            ($t -replace '/', [System.IO.Path]::DirectorySeparatorChar)
        )
    )
}

function Get-IOSSocksPhoneHost {
    param([string] $Override = '')
    if (-not [string]::IsNullOrWhiteSpace($Override)) {
        return $Override.Trim()
    }
    $s = Get-IOSSocksWindowsSettings
    $ip = [string]$s.phoneLanHost
    if (-not [string]::IsNullOrWhiteSpace($ip)) { return $ip.Trim() }
    return '172.20.10.1'
}

function Get-IOSSocksPacUrl {
    param(
        [string] $PhoneHost = '',
        [int] $WpadPort = 0,
        [string] $PacUrlOverride = ''
    )
    if (-not [string]::IsNullOrWhiteSpace($PacUrlOverride)) {
        return $PacUrlOverride.Trim()
    }
    $s = Get-IOSSocksWindowsSettings
    $ip = Get-IOSSocksPhoneHost -Override $PhoneHost
    $port = if ($WpadPort -gt 0) { $WpadPort } else { [int]$s.wpadPort }
    if ($port -le 0) { $port = 8088 }
    return "http://${ip}:${port}/wpad.dat"
}

function Get-IOSSocksLanDebugUrl {
    param([string] $PhoneHost = '')
    $s = Get-IOSSocksWindowsSettings
    $ip = Get-IOSSocksPhoneHost -Override $PhoneHost
    $port = [int]$s.lanDebugPort
    if ($port -le 0) { $port = 8765 }
    return "http://${ip}:${port}/"
}

function Show-IOSSocksWindowsDiagnostics {
    $path = Get-IOSSocksWindowsConfigPath
    $s = Get-IOSSocksWindowsSettings
    Write-Host "Config: $path ($(if (Test-Path -LiteralPath $path) { 'exists' } else { 'missing — run Set-IOSSocksWindows.ps1' }))"
    Write-Host "  phoneLanHost:    $(if ($s.phoneLanHost) { $s.phoneLanHost } else { '(not set)' })"
    Write-Host "  wpadPort:        $($s.wpadPort)"
    Write-Host "  socksPort:       $($s.socksPort)"
    Write-Host "  httpPort:        $($s.httpPort)"
    Write-Host "  lanDebugPort:    $($s.lanDebugPort)"
    Write-Host "  iCloudDownloads: $(if ($s.iCloudDownloads) { $s.iCloudDownloads } else { '(default in deploy.ps1)' })"
    Write-Host "  PAC URL:         $(Get-IOSSocksPacUrl)"
    Write-Host "  LAN debug:       $(Get-IOSSocksLanDebugUrl)"
    Write-Host "  potPlayerProxy:  $($s.potPlayerProxy)"
    if ($s.potPlayerRegKey) { Write-Host "  potPlayerRegKey: $($s.potPlayerRegKey)" }
}
