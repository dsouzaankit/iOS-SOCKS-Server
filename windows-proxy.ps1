# Forwarder — script moved to windows\windows-proxy.ps1
& "$PSScriptRoot\windows\windows-proxy.ps1" @args
if ($LASTEXITCODE) { exit $LASTEXITCODE }
