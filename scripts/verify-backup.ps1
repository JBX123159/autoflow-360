$ErrorActionPreference = "Stop"

function Test-DockerDaemon {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $null = @(& $Command @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    return $exitCode -eq 0
}

function Read-LocalSettings {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)

    $settings = @{
        Site = "autoflow.localhost"
        Runtime = ".runtime/frappe_docker"
        WslDistro = "Ubuntu"
    }
    $allowedKeys = @(
        "AUTOFLOW_SITE",
        "AUTOFLOW_ADMIN_PASSWORD",
        "AUTOFLOW_RUNTIME",
        "AUTOFLOW_WSL_DISTRO"
    )
    $envFile = Join-Path $ProjectRoot ".env"
    if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
        return $settings
    }

    $seenKeys = @{}
    $lineNumber = 0
    $content = [System.IO.File]::ReadAllText($envFile, [System.Text.Encoding]::UTF8)
    if ($content.IndexOf([char]0) -ge 0) {
        throw ".env contains a NUL character."
    }
    foreach ($line in [regex]::Split($content, "\r?\n")) {
        $lineNumber += 1
        if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith("#")) {
            continue
        }
        if ($line -notmatch "^([A-Z][A-Z0-9_]*)=(.*)$") {
            throw ".env line $lineNumber must use KEY=value."
        }
        $key = $Matches[1]
        $value = $Matches[2]
        if ($allowedKeys -notcontains $key) {
            throw ".env line $lineNumber contains an unsupported key: $key."
        }
        if ($seenKeys.ContainsKey($key)) {
            throw ".env line $lineNumber repeats key: $key."
        }
        $seenKeys[$key] = $true
        if ($key -eq "AUTOFLOW_SITE") { $settings.Site = $value }
        if ($key -eq "AUTOFLOW_RUNTIME") { $settings.Runtime = $value }
        if ($key -eq "AUTOFLOW_WSL_DISTRO") { $settings.WslDistro = $value }
    }
    return $settings
}

function Convert-ToDockerPath {
    param(
        [Parameter(Mandatory = $true)][string]$WindowsPath,
        [Parameter(Mandatory = $true)][hashtable]$Backend
    )

    if ($Backend.Name -eq "Windows") {
        return $WindowsPath.Replace("\", "/")
    }
    $normalizedPath = $WindowsPath.Replace("\", "/")
    $output = @(& $Backend.Command -d $Backend.WslDistro -- wslpath -a $normalizedPath 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to convert the project path for WSL."
    }
    $convertedPath = ($output | Select-Object -Last 1).ToString().Trim()
    if ($convertedPath -notmatch "^/[^`r`n]*$") {
        throw "WSL returned an invalid path."
    }
    return $convertedPath
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$settings = Read-LocalSettings -ProjectRoot $projectRoot
if ($settings.Site -notmatch "^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+localhost$") {
    throw "AUTOFLOW_SITE must be a lowercase .localhost name."
}
if ($settings.WslDistro -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$") {
    throw "AUTOFLOW_WSL_DISTRO is invalid."
}

$localDocker = Get-Command docker -ErrorAction SilentlyContinue
if ($null -ne $localDocker -and (Test-DockerDaemon -Command $localDocker.Source -Arguments @("info"))) {
    $backend = @{ Name = "Windows"; Command = $localDocker.Source; Prefix = @(); WslDistro = $null }
}
else {
    $wsl = Get-Command wsl -ErrorAction SilentlyContinue
    if ($null -eq $wsl) {
        throw "Docker is unavailable and WSL was not found."
    }
    $dockerArguments = @("-d", $settings.WslDistro, "--", "docker", "info")
    if (-not (Test-DockerDaemon -Command $wsl.Source -Arguments $dockerArguments)) {
        throw "Docker daemon is unavailable in Windows and WSL."
    }
    $backend = @{
        Name = "WSL2"
        Command = $wsl.Source
        Prefix = @("-d", $settings.WslDistro, "--", "docker")
        WslDistro = $settings.WslDistro
    }
}

$runtimeCandidate = if ([System.IO.Path]::IsPathRooted($settings.Runtime)) {
    $settings.Runtime
}
else {
    Join-Path $projectRoot $settings.Runtime
}
$runtimeRoot = [System.IO.Path]::GetFullPath($runtimeCandidate)
$projectPrefix = $projectRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
if (-not $runtimeRoot.StartsWith($projectPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "AUTOFLOW_RUNTIME must stay inside the current repository."
}

$composeFile = Join-Path $runtimeRoot ".devcontainer\docker-compose.yml"
$overrideFile = Join-Path $runtimeRoot ".devcontainer\compose.autoflow.yaml"
if (-not (Test-Path -LiteralPath $composeFile -PathType Leaf)) {
    throw "Local development Compose file is missing. Run bootstrap-dev.ps1 first."
}
if (-not (Test-Path -LiteralPath $overrideFile -PathType Leaf)) {
    throw "AutoFlow Compose override is missing. Run bootstrap-dev.ps1 first."
}

$composeForDocker = Convert-ToDockerPath -WindowsPath $composeFile -Backend $backend
$overrideForDocker = Convert-ToDockerPath -WindowsPath $overrideFile -Backend $backend
$dockerArguments = @($backend.Prefix) + @(
    "compose", "-f", $composeForDocker, "-f", $overrideForDocker,
    "exec", "-T", "frappe", "bash", "/workspace/autoflow_360/scripts/verify-backup.sh", $settings.Site
)

Write-Host "Running backup and disposable-site restore verification..."
& $backend.Command @dockerArguments
if ($LASTEXITCODE -ne 0) {
    throw "Backup and restore verification failed with exit code $LASTEXITCODE."
}
