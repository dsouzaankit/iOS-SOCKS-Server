#Requires -Version 5.1
# PotPlayer proxy toggle via registry snapshot diff (F5 -> Network -> Proxy server).
# One-time calibration: PotPlayer-Proxy-Calibrate.cmd (this folder)

. "$PSScriptRoot\..\IOS-Socks-Windows.ps1"

function Get-PotPlayerProxyProfileDir {
    Join-Path $env:LOCALAPPDATA 'iOS-SOCKS-Server\potplayer'
}

function Get-PotPlayerRegistryRoot {
    $s = Get-IOSSocksWindowsSettings
    $key = [string]$s.potPlayerRegKey
    if ([string]::IsNullOrWhiteSpace($key)) { $key = 'PotPlayerMini64' }
    if ($key -match '^HKCU:\\') { return $key.TrimEnd('\') }
    return "HKCU:\Software\Daum\$($key.Trim('\'))"
}

function Get-PotPlayerSettingsRegPath {
    Join-Path (Get-PotPlayerRegistryRoot) 'Settings'
}

function Test-PotPlayerRegistryInstalled {
    Test-Path -LiteralPath (Get-PotPlayerSettingsRegPath)
}

function Test-PotPlayerProxyEnabledInConfig {
    $s = Get-IOSSocksWindowsSettings
    return [bool]$s.potPlayerProxy
}

function Get-PotPlayerProxyPatchPath {
    param([ValidateSet('on', 'off')] [string] $State)
    Join-Path (Get-PotPlayerProxyProfileDir) "proxy-patch-$State.json"
}

function Get-PotPlayerProxySnapshotPath {
    param([ValidateSet('on', 'off')] [string] $State)
    Join-Path (Get-PotPlayerProxyProfileDir) "settings-$State.json"
}

function Export-PotPlayerSettingsSnapshot {
    $regPath = Get-PotPlayerSettingsRegPath
    if (-not (Test-Path -LiteralPath $regPath)) {
        throw "PotPlayer Settings key not found: $regPath"
    }
    $props = Get-ItemProperty -LiteralPath $regPath
    $out = [ordered]@{
        regPath   = $regPath
        captured  = (Get-Date).ToString('o')
        values    = [ordered]@{}
    }
    foreach ($name in $props.PSObject.Properties.Name) {
        if ($name -match '^PS') { continue }
        $val = $props.$name
        if ($val -is [byte[]]) {
            $out.values[$name] = @{ type = 'binary'; data = [Convert]::ToBase64String($val) }
        } elseif ($val -is [int] -or $val -is [long]) {
            $out.values[$name] = @{ type = 'dword'; data = [int]$val }
        } else {
            $out.values[$name] = @{ type = 'string'; data = [string]$val }
        }
    }
    return $out
}

function Save-PotPlayerSettingsSnapshot {
    param(
        [ValidateSet('on', 'off')]
        [string] $State
    )
    $dir = Get-PotPlayerProxyProfileDir
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $snap = Export-PotPlayerSettingsSnapshot
    $path = Get-PotPlayerProxySnapshotPath -State $State
    $snap | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $path -Encoding UTF8
    Write-Host "Saved snapshot: $path"
    return $path
}

function Get-PotPlayerProxyDiffKeys {
    param(
        $OffSnapshot,
        $OnSnapshot
    )
    $keys = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($name in $OffSnapshot.values.PSObject.Properties.Name) {
        [void]$keys.Add($name)
    }
    foreach ($name in $OnSnapshot.values.PSObject.Properties.Name) {
        [void]$keys.Add($name)
    }
    $changed = @()
    foreach ($name in $keys) {
        $offEntry = $OffSnapshot.values.$name
        $onEntry = $OnSnapshot.values.$name
        $offJson = if ($offEntry) { ($offEntry | ConvertTo-Json -Compress) } else { '' }
        $onJson = if ($onEntry) { ($onEntry | ConvertTo-Json -Compress) } else { '' }
        if ($offJson -ne $onJson) { $changed += $name }
    }
    return $changed
}

function Build-PotPlayerProxyPatch {
    param(
        $Snapshot,
        [string[]] $Keys
    )
    $patch = [ordered]@{
        regPath = $Snapshot.regPath
        keys    = [ordered]@{}
    }
    foreach ($key in $Keys) {
        $entry = $Snapshot.values.$key
        if ($null -eq $entry) { continue }
        $patch.keys[$key] = $entry
    }
    return $patch
}

function Save-PotPlayerProxyPatchesFromSnapshots {
    $offPath = Get-PotPlayerProxySnapshotPath -State off
    $onPath = Get-PotPlayerProxySnapshotPath -State on
    if (-not (Test-Path -LiteralPath $offPath) -or -not (Test-Path -LiteralPath $onPath)) {
        throw 'Missing snapshots. Run PotPlayer-Proxy-Calibrate.cmd (or -Off / -On) first.'
    }
    $off = Get-Content -LiteralPath $offPath -Raw | ConvertFrom-Json
    $on = Get-Content -LiteralPath $onPath -Raw | ConvertFrom-Json
    $diffKeys = Get-PotPlayerProxyDiffKeys -OffSnapshot $off -OnSnapshot $on
    if ($diffKeys.Count -eq 0) {
        throw 'No registry differences between OFF and ON snapshots. Configure proxy in PotPlayer (F5 -> Network) before the ON snapshot.'
    }
    $patchOff = Build-PotPlayerProxyPatch -Snapshot $off -Keys $diffKeys
    $patchOn = Build-PotPlayerProxyPatch -Snapshot $on -Keys $diffKeys
    $patchOff | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Get-PotPlayerProxyPatchPath -State off) -Encoding UTF8
    $patchOn | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Get-PotPlayerProxyPatchPath -State on) -Encoding UTF8
    Write-Host "Proxy patch keys ($($diffKeys.Count)): $($diffKeys -join ', ')"
    return $diffKeys
}

function Test-PotPlayerProxyProfilesReady {
    (Test-Path -LiteralPath (Get-PotPlayerProxyPatchPath -State on)) -and
        (Test-Path -LiteralPath (Get-PotPlayerProxyPatchPath -State off))
}

function Set-PotPlayerRegistryValue {
    param(
        [string] $RegPath,
        [string] $Name,
        $Entry
    )
    switch ($Entry.type) {
        'dword' {
            Set-ItemProperty -LiteralPath $RegPath -Name $Name -Type DWord -Value ([int]$Entry.data)
        }
        'binary' {
            $bytes = [Convert]::FromBase64String([string]$Entry.data)
            Set-ItemProperty -LiteralPath $RegPath -Name $Name -Type Binary -Value $bytes
        }
        default {
            Set-ItemProperty -LiteralPath $RegPath -Name $Name -Type String -Value ([string]$Entry.data)
        }
    }
}

function Apply-PotPlayerProxyPatch {
    param([ValidateSet('on', 'off')] [string] $State)
    $patchPath = Get-PotPlayerProxyPatchPath -State $State
    if (-not (Test-Path -LiteralPath $patchPath)) {
        throw "Missing patch file: $patchPath (run potplayer\PotPlayer-Proxy-Calibrate.cmd)"
    }
    $patch = Get-Content -LiteralPath $patchPath -Raw | ConvertFrom-Json
    $regPath = [string]$patch.regPath
    if (-not (Test-Path -LiteralPath $regPath)) {
        throw "PotPlayer Settings key not found: $regPath"
    }
    foreach ($prop in $patch.keys.PSObject.Properties) {
        Set-PotPlayerRegistryValue -RegPath $regPath -Name $prop.Name -Entry $prop.Value
    }
}

function Set-PotPlayerProxyState {
    param([ValidateSet('on', 'off')] [string] $State)
    if (-not (Test-PotPlayerProxyEnabledInConfig)) { return $null }
    if (-not (Test-PotPlayerRegistryInstalled)) {
        Write-Warning 'PotPlayer registry not found; skipping PotPlayer proxy toggle.'
        return 'skipped (not installed)'
    }
    if (-not (Test-PotPlayerProxyProfilesReady)) {
        Write-Warning 'PotPlayer proxy profiles missing. Run: windows\potplayer\PotPlayer-Proxy-Calibrate.cmd'
        return 'skipped (not calibrated)'
    }
    Apply-PotPlayerProxyPatch -State $State
    return "potplayer proxy $State ($((Get-PotPlayerProxyPatchPath -State $State)))"
}

function Show-PotPlayerProxyStatus {
    $root = Get-PotPlayerRegistryRoot
    Write-Host 'PotPlayer:'
    Write-Host "  registry:       $root"
    Write-Host "  toggle in cmd:  $(if (Test-PotPlayerProxyEnabledInConfig) { 'enabled in ios-socks-windows.json' } else { 'disabled (set potPlayerProxy: true)' })"
    Write-Host "  profiles ready: $(Test-PotPlayerProxyProfilesReady)"
    if (Test-PotPlayerProxyProfilesReady) {
        $on = Get-Content -LiteralPath (Get-PotPlayerProxyPatchPath -State on) -Raw | ConvertFrom-Json
        $keys = @($on.keys.PSObject.Properties.Name)
        Write-Host "  patch keys:     $($keys -join ', ')"
    }
    Write-Host "  profile folder: $(Get-PotPlayerProxyProfileDir)"
}
