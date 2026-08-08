param(
    [string]$OriginUrl = "http://autoflow.localhost:8000"
)

$ErrorActionPreference = "Stop"

try {
    $origin = [Uri]$OriginUrl
}
catch {
    throw "OriginUrl must be a valid HTTP URL."
}
if ($origin.Scheme -ne "http") {
    throw "Quick Tunnel origin must use local HTTP."
}
if ($origin.Host -notin @("autoflow.localhost", "localhost", "127.0.0.1")) {
    throw "OriginUrl host must be autoflow.localhost, localhost, or 127.0.0.1."
}
if (-not $origin.IsDefaultPort -and ($origin.Port -lt 1 -or $origin.Port -gt 65535)) {
    throw "OriginUrl port is invalid."
}

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($null -eq $cloudflared) {
    throw "cloudflared is not installed. Follow docs/deployment/cloudflare-tunnel.md."
}

$healthUrl = $OriginUrl.TrimEnd("/") + "/api/method/ping"
try {
    $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 10
}
catch {
    throw "Local AutoFlow health check failed: $($_.Exception.Message)"
}
if ($response.StatusCode -ne 200) {
    throw "Local AutoFlow health check returned HTTP $($response.StatusCode)."
}

Write-Host "Starting a temporary Cloudflare Quick Tunnel. No uptime is guaranteed."
& $cloudflared.Source tunnel --url $OriginUrl
exit $LASTEXITCODE
