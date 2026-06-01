# One-off probe: find PotPlayer proxy settings in registry / INI (run locally).
$ErrorActionPreference = 'SilentlyContinue'
foreach ($key in @(
    'HKCU:\Software\Daum\PotPlayerMini64',
    'HKCU:\Software\Daum\PotPlayer64'
)) {
    if (-not (Test-Path -LiteralPath $key)) { continue }
    Write-Host "=== $key ==="
    Get-ChildItem -LiteralPath $key -Recurse | ForEach-Object {
        $p = Get-ItemProperty -LiteralPath $_.PSPath
        if (-not $p) { return }
        foreach ($prop in $p.PSObject.Properties) {
            if ($prop.Name -match '^PS') { continue }
            $v = [string]$prop.Value
            if ($prop.Name -match 'proxy|sock|http|net' -or $v -match 'proxy|sock|9876|9877|8088') {
                Write-Host ($_.PSPath + ' :: ' + $prop.Name + ' = ' + $v)
            }
        }
    }
}
$iniPaths = @(
    (Join-Path $env:APPDATA 'PotPlayerMini64\PotPlayerMini64.ini'),
    (Join-Path $env:LOCALAPPDATA 'PotPlayerMini64\PotPlayerMini64.ini'),
    (Join-Path $env:APPDATA 'PotPlayer\PotPlayerMini64.ini')
)
foreach ($ini in $iniPaths) {
    if (-not (Test-Path -LiteralPath $ini)) { continue }
    Write-Host "=== INI $ini ==="
    Select-String -LiteralPath $ini -Pattern 'proxy|sock' -CaseSensitive:$false | Select-Object -First 30
}
