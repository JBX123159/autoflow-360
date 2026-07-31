param(
    [string]$WslDistro = $env:AUTOFLOW_WSL_DISTRO
)

$ErrorActionPreference = "Stop"

function ConvertTo-CleanLines {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Output
    )

    $lines = @()
    foreach ($item in $Output) {
        if ($null -eq $item) {
            continue
        }

        $line = $item.ToString().Replace(([char]0).ToString(), "").Trim()
        if (-not [string]::IsNullOrWhiteSpace($line)) {
            $lines += $line
        }
    }
    return $lines
}

function Get-CommandVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$DisplayName
    )

    $resolved = Get-Command $Command -ErrorAction SilentlyContinue
    if ($null -eq $resolved) {
        return $null
    }

    $output = & $resolved.Source @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $lines = @(ConvertTo-CleanLines -Output @($output))
    if ($exitCode -ne 0) {
        $details = if ($lines.Count -gt 0) { $lines -join " " } else { "未返回错误详情" }
        throw "$DisplayName 版本检查失败：$details。请按 README.md 快速开始章节检查安装。"
    }
    if ($lines.Count -eq 0) {
        throw "$DisplayName 版本检查未返回内容。"
    }
    return $lines[0]
}

function Get-UbuntuWsl2Distro {
    param(
        [string]$RequestedDistro
    )

    $resolved = Get-Command "wsl" -ErrorAction SilentlyContinue
    if ($null -eq $resolved) {
        return $null
    }

    $output = & $resolved.Source --list --verbose 2>&1
    $exitCode = $LASTEXITCODE
    $lines = @(ConvertTo-CleanLines -Output @($output))
    if ($exitCode -ne 0) {
        $details = if ($lines.Count -gt 0) { $lines -join " " } else { "未返回错误详情" }
        throw "无法读取 WSL 发行版列表：$details。请按 README.md 快速开始章节安装 Ubuntu WSL2。"
    }

    $ubuntuDistributions = @()
    foreach ($line in $lines) {
        $normalized = [regex]::Replace($line, "^\s*\*?\s*", "")
        $columns = @($normalized -split "\s+")
        if ($columns.Count -lt 3) {
            continue
        }
        if ($columns[0] -match "^Ubuntu(?:-.+)?$") {
            $ubuntuDistributions += [pscustomobject]@{
                Name = $columns[0]
                Version = $columns[$columns.Count - 1]
            }
        }
    }

    if ($ubuntuDistributions.Count -eq 0) {
        throw "WSL 中未安装 Ubuntu 发行版。请按 README.md 快速开始章节安装 Ubuntu WSL2。"
    }

    $selected = $null
    if (-not [string]::IsNullOrWhiteSpace($RequestedDistro)) {
        if ($RequestedDistro -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$") {
            throw "AUTOFLOW_WSL_DISTRO 不合法，只允许字母、数字、点、下划线和连字符。"
        }
        $selected = $ubuntuDistributions |
            Where-Object { $_.Name -eq $RequestedDistro } |
            Select-Object -First 1
        if ($null -eq $selected) {
            throw "WSL 中找不到指定的 Ubuntu 发行版：$RequestedDistro。"
        }
    }
    else {
        $selected = $ubuntuDistributions |
            Where-Object { $_.Version -eq "2" } |
            Select-Object -First 1
        if ($null -eq $selected) {
            $selected = $ubuntuDistributions | Select-Object -First 1
        }
    }

    if ($selected.Version -ne "2") {
        throw "Ubuntu 发行版必须使用 WSL2；$($selected.Name) 当前 VERSION 为：$($selected.Version)。"
    }
    return $selected.Name
}

function Get-WslCommandVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Distro,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $resolved = Get-Command "wsl" -ErrorAction SilentlyContinue
    if ($null -eq $resolved) {
        return $null
    }

    $output = & $resolved.Source -d $Distro -- $Command @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $lines = @(ConvertTo-CleanLines -Output @($output))
    if ($exitCode -ne 0 -or $lines.Count -eq 0) {
        return $null
    }
    return $lines[0]
}

function Test-CommandSuccess {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $resolved = Get-Command $Command -ErrorAction SilentlyContinue
    if ($null -eq $resolved) {
        return $false
    }

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $null = @(& $resolved.Source @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return $exitCode -eq 0
}

$resolvedWslDistro = Get-UbuntuWsl2Distro -RequestedDistro $WslDistro
$localDocker = Get-Command "docker" -ErrorAction SilentlyContinue
$localDockerDaemonAvailable = (
    $null -ne $localDocker -and
    (Test-CommandSuccess `
        -Command $localDocker.Source `
        -Arguments @("info", "--format", "{{.ServerVersion}}"))
)
$wslDockerDaemonAvailable = (
    -not [string]::IsNullOrWhiteSpace($resolvedWslDistro) -and
    (Test-CommandSuccess `
        -Command "wsl" `
        -Arguments @(
            "-d",
            $resolvedWslDistro,
            "--",
            "docker",
            "info",
            "--format",
            "{{.ServerVersion}}"
        ))
)
$dockerBackend = if ($localDockerDaemonAvailable) {
    "Windows"
}
elseif ($wslDockerDaemonAvailable) {
    "WSL2"
}
else {
    $null
}

$results = [ordered]@{
    git = if ($dockerBackend -eq "Windows" -or [string]::IsNullOrWhiteSpace($dockerBackend)) {
        Get-CommandVersion -Command "git" -Arguments @("--version") -DisplayName "Git"
    }
    elseif (-not [string]::IsNullOrWhiteSpace($resolvedWslDistro)) {
        Get-WslCommandVersion `
            -Distro $resolvedWslDistro `
            -Command "git" `
            -Arguments @("--version")
    }
    else { $null }
    docker = if ($dockerBackend -eq "Windows") {
        Get-CommandVersion -Command "docker" -Arguments @("--version") -DisplayName "Docker Engine"
    }
    elseif ($dockerBackend -eq "WSL2") {
        Get-WslCommandVersion `
            -Distro $resolvedWslDistro `
            -Command "docker" `
            -Arguments @("--version")
    }
    else { $null }
    compose = if ($dockerBackend -eq "Windows") {
        Get-CommandVersion -Command "docker" -Arguments @("compose", "version") -DisplayName "Docker Compose"
    }
    elseif ($dockerBackend -eq "WSL2") {
        Get-WslCommandVersion `
            -Distro $resolvedWslDistro `
            -Command "docker" `
            -Arguments @("compose", "version")
    }
    else { $null }
    wsl = Get-CommandVersion -Command "wsl" -Arguments @("--version") -DisplayName "WSL"
}

$labels = @{
    git = "Git"
    docker = "Docker Engine"
    compose = "Docker Compose"
    wsl = "WSL"
}
$missing = @($results.GetEnumerator() | Where-Object { [string]::IsNullOrWhiteSpace($_.Value) })
foreach ($item in $results.GetEnumerator()) {
    $value = if ($item.Value) { $item.Value } else { "未安装" }
    Write-Host ("{0,-10} {1}" -f $item.Key, $value)
}

if ($missing.Count -gt 0) {
    $names = @($missing | ForEach-Object { $labels[$_.Name] }) -join "、"
    throw "缺少运行环境：$names。请按 README.md 快速开始章节安装后重试。"
}

$dockerVersionMatch = [regex]::Match($results.docker, "\d+")
if (-not $dockerVersionMatch.Success) {
    throw "无法识别 Docker Engine 版本：$($results.docker)"
}

$dockerMajor = [int]$dockerVersionMatch.Value
if ($dockerMajor -lt 23) {
    throw "Docker Engine 需要 23 或更高版本，当前为：$($results.docker)"
}

$composeVersionMatch = [regex]::Match(
    $results.compose,
    "(?i)\bversion\s+v?(\d+)(?:\.\d+)*\b"
)
if (-not $composeVersionMatch.Success) {
    throw "无法识别 Docker Compose 版本：$($results.compose)"
}

$composeMajor = [int]$composeVersionMatch.Groups[1].Value
if ($composeMajor -lt 2) {
    throw "Docker Compose 需要 v2 或更高版本，当前为：$($results.compose)"
}

Write-Host ("{0,-10} {1} (VERSION 2)" -f "ubuntu", $resolvedWslDistro)
Write-Host ("{0,-10} {1}" -f "backend", $dockerBackend)
Write-Host "环境体检通过。" -ForegroundColor Green
