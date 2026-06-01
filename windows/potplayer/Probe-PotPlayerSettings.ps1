# Dump all registry value names under PotPlayerMini64 (find proxy-related keys).
$root = 'HKCU:\Software\Daum\PotPlayerMini64'
if (-not (Test-Path -LiteralPath $root)) { Write-Host 'No PotPlayerMini64 key'; exit 0 }
Get-ChildItem -LiteralPath $root -Recurse | ForEach-Object {
    $item = $_
    try {
        $props = Get-ItemProperty -LiteralPath $item.PSPath -ErrorAction Stop
    } catch { return }
    foreach ($prop in $props.PSObject.Properties) {
        if ($prop.Name -match '^PS') { continue }
        Write-Output ('{0}|{1}|{2}' -f $item.PSPath, $prop.Name, $prop.Value)
    }
} | Out-File -FilePath (Join-Path $PSScriptRoot 'potplayer-reg-dump.txt') -Encoding utf8
Write-Host 'Wrote potplayer-reg-dump.txt'
