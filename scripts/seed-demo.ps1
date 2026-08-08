param(
    [ValidateNotNullOrEmpty()]
    [string]$Site = "autoflow.localhost"
)

$ErrorActionPreference = "Stop"

$benchScript = Join-Path $PSScriptRoot "bench.ps1"
if (-not (Test-Path -LiteralPath $benchScript -PathType Leaf)) {
    throw "Bench wrapper script was not found: $benchScript"
}

& $benchScript `
    --site $Site execute autoflow_360.demo.seed.seed_demo_data

if ($LASTEXITCODE -ne 0) {
    throw "Demo data initialization failed for site: $Site"
}

Write-Host "AutoFlow 360 CNY demo scenarios are ready for site: $Site"
