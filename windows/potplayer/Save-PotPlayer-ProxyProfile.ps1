#Requires -Version 5.1
# One-time calibration for PotPlayer proxy toggle (used by Socks-Proxy-On/Off.cmd).
#
# One-click: double-click PotPlayer-Proxy-Calibrate.cmd (this folder)
# Config: ..\ios-socks-windows.json

param(
    [ValidateSet('Off', 'On', 'Build', 'Status', 'Wizard')]
    [string] $Step = 'Status'
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\IOS-Socks-Windows.ps1"
. "$PSScriptRoot\PotPlayer-ProxySettings.ps1"

function Confirm-PotPlayerClosed {
    $procs = Get-Process -Name 'PotPlayerMini64', 'PotPlayerMini', 'PotPlayer64' -ErrorAction SilentlyContinue
    if ($procs) {
        throw "Close PotPlayer first (running: $($procs.Name -join ', '))"
    }
}

function Show-PotPlayerCalibrationHints {
    $s = Get-IOSSocksWindowsSettings
    $hostIp = Get-IOSSocksPhoneHost
    Write-Host '=== PotPlayer proxy calibration ==='
    Write-Host ''
    Write-Host 'In PotPlayer: F5 -> Network -> Proxy server'
    Write-Host "  ON:  SOCKS5, server $hostIp, port $($s.socksPort)"
    Write-Host "       (or HTTP port $($s.httpPort))"
    Write-Host '  OFF: disable / clear proxy'
    Write-Host ''
    Write-Host 'Close PotPlayer completely before each snapshot (check Task Manager).'
    Write-Host ''
}

function Wait-CalibrationContinue {
    param([string] $Prompt)
    Read-Host $Prompt
}

function Invoke-PotPlayerCalibrationWizard {
    Show-PotPlayerCalibrationHints
    if (-not (Test-PotPlayerRegistryInstalled)) {
        throw 'PotPlayer registry not found. Install PotPlayer and open it once, then run calibration again.'
    }

    Wait-CalibrationContinue 'Step 1/3: Set proxy OFF in PotPlayer, close PotPlayer, then press Enter'
    Confirm-PotPlayerClosed
    Save-PotPlayerSettingsSnapshot -State off
    Write-Host 'Saved OFF snapshot.'
    Write-Host ''

    Wait-CalibrationContinue 'Step 2/3: Set proxy ON (see above), close PotPlayer, then press Enter'
    Confirm-PotPlayerClosed
    Save-PotPlayerSettingsSnapshot -State on
    Write-Host 'Saved ON snapshot.'
    Write-Host ''

    Write-Host 'Step 3/3: Building registry patches...'
    $keys = Save-PotPlayerProxyPatchesFromSnapshots
    Write-Host "Patch keys: $($keys -join ', ')"
    Write-Host ''

    $answer = Read-Host 'Enable potPlayerProxy in ios-socks-windows.json? [Y/n]'
    if ($answer -notmatch '^[nN]') {
        $settings = Get-IOSSocksWindowsSettings
        $settings.potPlayerProxy = $true
        Save-IOSSocksWindowsSettings -Settings $settings
        Write-Host 'potPlayerProxy enabled in config.'
    } else {
        Write-Host 'Skipped config. Set "potPlayerProxy": true manually when ready.'
    }
    Write-Host ''
    Write-Host 'Done. Use ..\Socks-Proxy-On.cmd / Off.cmd (restart PotPlayer if it was open).'
}

switch ($Step) {
    'Status' {
        Show-PotPlayerProxyStatus
        $s = Get-IOSSocksWindowsSettings
        Write-Host ''
        Write-Host 'Suggested ON proxy in PotPlayer UI:'
        Write-Host "  Type:   SOCKS5 (or HTTP if you prefer port $($s.httpPort))"
        Write-Host "  Server: $(Get-IOSSocksPhoneHost)"
        Write-Host "  Port:   $($s.socksPort) (SOCKS) / $($s.httpPort) (HTTP)"
    }
    'Off' {
        Confirm-PotPlayerClosed
        Save-PotPlayerSettingsSnapshot -State off
        Write-Host 'Next: enable proxy in PotPlayer, then run PotPlayer-Proxy-Calibrate-On.cmd'
    }
    'On' {
        Confirm-PotPlayerClosed
        Save-PotPlayerSettingsSnapshot -State on
        Write-Host 'Next: run PotPlayer-Proxy-Calibrate-Build.cmd'
    }
    'Build' {
        $keys = Save-PotPlayerProxyPatchesFromSnapshots
        Write-Host "Patch keys: $($keys -join ', ')"
        Write-Host ''
        $answer = Read-Host 'Enable potPlayerProxy in ios-socks-windows.json? [Y/n]'
        if ($answer -notmatch '^[nN]') {
            $settings = Get-IOSSocksWindowsSettings
            $settings.potPlayerProxy = $true
            Save-IOSSocksWindowsSettings -Settings $settings
            Write-Host 'potPlayerProxy enabled in config.'
        }
        Write-Host ''
        Write-Host 'Done. Use ..\Socks-Proxy-On.cmd / Off.cmd (restart PotPlayer if it was open).'
    }
    'Wizard' {
        Invoke-PotPlayerCalibrationWizard
    }
}
