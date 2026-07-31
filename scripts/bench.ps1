$ErrorActionPreference = "Stop"

function Read-RuntimeSetting {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot
    )

    $allowedKeys = @(
        "AUTOFLOW_SITE",
        "AUTOFLOW_ADMIN_PASSWORD",
        "AUTOFLOW_RUNTIME",
        "AUTOFLOW_WSL_DISTRO"
    )
    $settings = @{
        Runtime = ".runtime/frappe_docker"
        WslDistro = "Ubuntu"
    }
    $envFile = Join-Path $ProjectRoot ".env"

    if (Test-Path -LiteralPath $envFile -PathType Leaf) {
        $rawContent = [System.IO.File]::ReadAllText(
            $envFile,
            [System.Text.Encoding]::UTF8
        )
        if ($rawContent.IndexOf([char]0) -ge 0) {
            throw ".env 含有 NUL 字符，已拒绝读取。"
        }

        $seenKeys = @{}
        $lineNumber = 0
        foreach ($line in [regex]::Split($rawContent, "\r?\n")) {
            $lineNumber += 1
            if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith("#")) {
                continue
            }
            if ($line -notmatch "^([A-Z][A-Z0-9_]*)=(.*)$") {
                throw ".env 第 $lineNumber 行格式错误，必须使用 KEY=value。"
            }

            $key = $Matches[1]
            $value = $Matches[2]
            if ($allowedKeys -notcontains $key) {
                throw ".env 第 $lineNumber 行包含不支持的配置项：$key。"
            }
            if ($seenKeys.ContainsKey($key)) {
                throw ".env 第 $lineNumber 行重复定义配置项：$key。"
            }
            if ($value.IndexOf([char]0) -ge 0 -or $value.Contains("`r") -or $value.Contains("`n")) {
                throw ".env 第 $lineNumber 行的值包含换行或 NUL 字符。"
            }

            $seenKeys[$key] = $true
            if ($key -eq "AUTOFLOW_RUNTIME") {
                $settings.Runtime = $value
            }
            if ($key -eq "AUTOFLOW_WSL_DISTRO") {
                $settings.WslDistro = $value
            }
        }
    }

    $environmentRuntime = [Environment]::GetEnvironmentVariable(
        "AUTOFLOW_RUNTIME",
        "Process"
    )
    if ($null -ne $environmentRuntime) {
        if (
            $environmentRuntime.IndexOf([char]0) -ge 0 -or
            $environmentRuntime.Contains("`r") -or
            $environmentRuntime.Contains("`n")
        ) {
            throw "环境变量 AUTOFLOW_RUNTIME 包含换行或 NUL 字符。"
        }
        $settings.Runtime = $environmentRuntime
    }

    $environmentWslDistro = [Environment]::GetEnvironmentVariable(
        "AUTOFLOW_WSL_DISTRO",
        "Process"
    )
    if ($null -ne $environmentWslDistro) {
        if (
            $environmentWslDistro.IndexOf([char]0) -ge 0 -or
            $environmentWslDistro.Contains("`r") -or
            $environmentWslDistro.Contains("`n")
        ) {
            throw "环境变量 AUTOFLOW_WSL_DISTRO 包含换行或 NUL 字符。"
        }
        $settings.WslDistro = $environmentWslDistro
    }

    return $settings
}

function Get-DockerBackend {
    param(
        [Parameter(Mandatory = $true)][string]$WslDistro
    )

    $localDocker = Get-Command "docker" -ErrorAction SilentlyContinue
    if (
        $null -ne $localDocker -and
        (Test-DockerDaemon `
            -Command $localDocker.Source `
            -Arguments @("info", "--format", "{{.ServerVersion}}"))
    ) {
        return @{
            Name = "Windows"
            Command = $localDocker.Source
            Prefix = @()
            WslDistro = $null
        }
    }

    $wslCommand = Get-Command "wsl" -ErrorAction SilentlyContinue
    if ($null -eq $wslCommand) {
        throw "Windows Docker 不可用，并且找不到 WSL。"
    }
    if (-not (Test-DockerDaemon `
        -Command $wslCommand.Source `
        -Arguments @(
            "-d",
            $WslDistro,
            "--",
            "docker",
            "info",
            "--format",
            "{{.ServerVersion}}"
        )
    )) {
        throw "Windows Docker daemon 不可用，并且 WSL 发行版 $WslDistro 中的 Docker daemon 也不可用。"
    }
    return @{
        Name = "WSL2"
        Command = $wslCommand.Source
        Prefix = @("-d", $WslDistro, "--", "docker")
        WslDistro = $WslDistro
    }
}

function Test-DockerDaemon {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $null = @(& $Command @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return $exitCode -eq 0
}

function Convert-ToDockerPath {
    param(
        [Parameter(Mandatory = $true)][string]$WindowsPath,
        [Parameter(Mandatory = $true)][hashtable]$DockerBackend
    )

    if ($DockerBackend.Name -eq "Windows") {
        return $WindowsPath.Replace("\", "/")
    }

    $normalizedWindowsPath = $WindowsPath.Replace("\", "/")
    $output = @(
        & $DockerBackend.Command `
            -d $DockerBackend.WslDistro `
            -- wslpath -a $normalizedWindowsPath 2>&1
    )
    if ($LASTEXITCODE -ne 0) {
        $details = ($output | ForEach-Object { $_.ToString().Trim() }) -join " "
        throw "把 Windows 路径转换为 WSL 路径失败：$details"
    }
    $convertedPath = ($output | Select-Object -Last 1).ToString().Trim()
    if ($convertedPath -notmatch "^/[^`r`n]*$") {
        throw "wslpath 返回了不合法路径：$convertedPath"
    }
    return $convertedPath
}

if ($args.Count -eq 0) {
    throw "缺少 Bench 参数。示例：.\scripts\bench.ps1 --site autoflow.localhost list-apps"
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$settings = Read-RuntimeSetting -ProjectRoot $projectRoot
$runtimeSetting = $settings.Runtime
$wslDistro = $settings.WslDistro
if ([string]::IsNullOrWhiteSpace($runtimeSetting)) {
    throw "AUTOFLOW_RUNTIME 不能为空。"
}
if ($wslDistro -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$") {
    throw "AUTOFLOW_WSL_DISTRO 不合法，只允许字母、数字、点、下划线和连字符。"
}
$dockerBackend = Get-DockerBackend -WslDistro $wslDistro

$runtimeCandidate = if ([System.IO.Path]::IsPathRooted($runtimeSetting)) {
    $runtimeSetting
}
else {
    Join-Path $projectRoot $runtimeSetting
}
$runtimeRoot = [System.IO.Path]::GetFullPath($runtimeCandidate)
$projectPrefix = $projectRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
if (-not $runtimeRoot.StartsWith($projectPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "AUTOFLOW_RUNTIME 必须位于当前仓库内：$projectRoot"
}

$composeRoot = Join-Path $runtimeRoot ".devcontainer"
$composeFile = Join-Path $composeRoot "docker-compose.yml"
$overrideFile = Join-Path $composeRoot "compose.autoflow.yaml"
if (
    -not (Test-Path -LiteralPath $composeFile -PathType Leaf) -or
    -not (Test-Path -LiteralPath $overrideFile -PathType Leaf)
) {
    throw "开发环境未初始化，请先运行 .\scripts\bootstrap-dev.ps1。"
}

$composeFileForDocker = Convert-ToDockerPath `
    -WindowsPath $composeFile `
    -DockerBackend $dockerBackend
$overrideFileForDocker = Convert-ToDockerPath `
    -WindowsPath $overrideFile `
    -DockerBackend $dockerBackend
$dockerPrefix = @($dockerBackend.Prefix)
$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $containerOutput = @(
        & $dockerBackend.Command @dockerPrefix compose `
            -f $composeFileForDocker `
            -f $overrideFileForDocker `
            ps -q frappe 2>&1
    )
    $containerExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if ($containerExitCode -ne 0) {
    $details = ($containerOutput | ForEach-Object { $_.ToString().Trim() }) -join " "
    throw "查询 Frappe 容器失败：$details"
}
$frappeContainer = @(
    $containerOutput |
        ForEach-Object { $_.ToString().Trim() } |
        Where-Object { $_ -match "^[0-9a-f]{12,64}$" }
) | Select-Object -Last 1
if ([string]::IsNullOrWhiteSpace($frappeContainer)) {
    throw "Frappe 容器未运行，请重新执行 .\scripts\bootstrap-dev.ps1。"
}

$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    & $dockerBackend.Command @dockerPrefix exec `
        --workdir "/workspace/development/frappe-bench" `
        $frappeContainer `
        bench @args
    $benchExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if ($benchExitCode -ne 0) {
    throw "Bench 命令执行失败，退出码：$benchExitCode。"
}
