$ErrorActionPreference = "Stop"

function Read-AutoFlowConfiguration {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot
    )

    $allowedKeys = @(
        "AUTOFLOW_SITE",
        "AUTOFLOW_ADMIN_PASSWORD",
        "AUTOFLOW_RUNTIME",
        "AUTOFLOW_WSL_DISTRO"
    )
    $values = @{
        AUTOFLOW_SITE = "autoflow.localhost"
        AUTOFLOW_ADMIN_PASSWORD = $null
        AUTOFLOW_RUNTIME = ".runtime/frappe_docker"
        AUTOFLOW_WSL_DISTRO = "Ubuntu"
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
            $values[$key] = $value
        }
    }

    foreach ($key in $allowedKeys) {
        $environmentValue = [Environment]::GetEnvironmentVariable($key, "Process")
        if ($null -ne $environmentValue) {
            if (
                $environmentValue.IndexOf([char]0) -ge 0 -or
                $environmentValue.Contains("`r") -or
                $environmentValue.Contains("`n")
            ) {
                throw "环境变量 $key 包含换行或 NUL 字符。"
            }
            $values[$key] = $environmentValue
        }
    }

    return $values
}

function Read-UpstreamLock {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot
    )

    $lockPath = Join-Path $ProjectRoot "deploy\upstream-lock.json"
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
        throw "缺少上游锁文件：$lockPath"
    }

    try {
        $lockData = (
            [System.IO.File]::ReadAllText(
                $lockPath,
                [System.Text.Encoding]::UTF8
            ) | ConvertFrom-Json
        )
    }
    catch {
        throw "上游锁文件不是合法 JSON：$($_.Exception.Message)"
    }

    $expectedEntries = @{
        frappe_docker = @{
            Repository = "https://github.com/frappe/frappe_docker"
            Branch = "main"
        }
        frappe = @{
            Repository = "https://github.com/frappe/frappe"
            Branch = "version-16"
        }
        erpnext = @{
            Repository = "https://github.com/frappe/erpnext"
            Branch = "version-16"
        }
        crm = @{
            Repository = "https://github.com/frappe/crm"
            Branch = "main"
        }
    }
    $actualEntryNames = @($lockData.PSObject.Properties.Name | Sort-Object)
    $expectedEntryNames = @($expectedEntries.Keys | Sort-Object)
    if (($actualEntryNames -join ",") -ne ($expectedEntryNames -join ",")) {
        throw "上游锁文件必须且只能包含：$($expectedEntryNames -join '、')。"
    }

    $validatedLock = @{}
    foreach ($entryName in $expectedEntryNames) {
        $entry = $lockData.PSObject.Properties[$entryName].Value
        $expected = $expectedEntries[$entryName]
        if ($entry.repository -ne $expected.Repository) {
            throw "上游锁文件中的 $entryName.repository 不是预期官方地址。"
        }
        if ($entry.branch -ne $expected.Branch) {
            throw "上游锁文件中的 $entryName.branch 必须为 $($expected.Branch)。"
        }
        if ($entry.commit -notmatch "^[0-9a-f]{40}$") {
            throw "上游锁文件中的 $entryName.commit 必须是 40 位小写 Git 哈希。"
        }
        $validatedLock[$entryName] = @{
            Repository = [string]$entry.repository
            Branch = [string]$entry.branch
            Commit = [string]$entry.commit
        }
    }
    return $validatedLock
}

function Read-ContainerImageLock {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot
    )

    $lockPath = Join-Path $ProjectRoot "deploy\container-lock.json"
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
        throw "缺少容器镜像锁文件：$lockPath"
    }
    try {
        $lockData = (
            [System.IO.File]::ReadAllText(
                $lockPath,
                [System.Text.Encoding]::UTF8
            ) | ConvertFrom-Json
        )
    }
    catch {
        throw "容器镜像锁文件不是合法 JSON：$($_.Exception.Message)"
    }

    $expectedRepositories = @{
        frappe_bench = "docker.io/frappe/bench"
        mariadb = "docker.io/mariadb"
        redis = "docker.io/redis"
    }
    $actualKeys = @($lockData.PSObject.Properties.Name | Sort-Object)
    $expectedKeys = @($expectedRepositories.Keys | Sort-Object)
    if (($actualKeys -join ",") -ne ($expectedKeys -join ",")) {
        throw "容器镜像锁文件必须且只能包含：$($expectedKeys -join '、')。"
    }

    $validatedLock = @{}
    foreach ($key in $expectedKeys) {
        $value = [string]$lockData.PSObject.Properties[$key].Value
        $expectedPattern = (
            "^" +
            [regex]::Escape($expectedRepositories[$key]) +
            "@sha256:[0-9a-f]{64}$"
        )
        if ($value -notmatch $expectedPattern) {
            throw "容器镜像锁中的 $key 必须是预期官方仓库的 sha256 摘要。"
        }
        $validatedLock[$key] = $value
    }
    return $validatedLock
}

function Get-RuntimePath {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][string]$ConfiguredPath
    )

    if ([string]::IsNullOrWhiteSpace($ConfiguredPath)) {
        throw "AUTOFLOW_RUNTIME 不能为空。"
    }

    $candidate = if ([System.IO.Path]::IsPathRooted($ConfiguredPath)) {
        $ConfiguredPath
    }
    else {
        Join-Path $ProjectRoot $ConfiguredPath
    }
    $fullPath = [System.IO.Path]::GetFullPath($candidate)
    $projectPrefix = $ProjectRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith($projectPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "AUTOFLOW_RUNTIME 必须位于当前仓库内：$ProjectRoot"
    }
    return $fullPath
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage,
        [switch]$CaptureOutput
    )

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 会把原生命令写入 stderr 的正常进度包装成
        # NativeCommandError；这里只按进程退出码判断，stderr 仍会被完整捕获。
        $ErrorActionPreference = "Continue"
        $output = @(& $Command @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        $details = @(
            $output |
                ForEach-Object { $_.ToString().Trim() } |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        ) -join " "
        if ([string]::IsNullOrWhiteSpace($details)) {
            $details = "未返回错误详情"
        }
        throw "$FailureMessage 退出码：$exitCode；详情：$details"
    }

    if ($CaptureOutput) {
        return $output
    }
    foreach ($line in $output) {
        Write-Host $line
    }
}

function Test-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Arguments
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

function Read-BenchVolumeOwner {
    param(
        [Parameter(Mandatory = $true)][hashtable]$DockerBackend,
        [Parameter(Mandatory = $true)][string]$BenchVolumeName,
        [Parameter(Mandatory = $true)][string]$FrappeBenchImage,
        [Parameter(Mandatory = $true)][string]$VolumeOwnerFile
    )

    $ownerOutput = @(
        Invoke-NativeCommand `
            -Command $DockerBackend.Command `
            -Arguments (
                $DockerBackend.Prefix +
                @(
                    "run",
                    "--rm",
                    "--mount",
                    "type=volume,source=$BenchVolumeName,target=/target",
                    $FrappeBenchImage,
                    "cat",
                    $VolumeOwnerFile
                )
            ) `
            -FailureMessage "读取 Bench 原生卷所有权标记失败。" `
            -CaptureOutput
    )
    $ownerLines = @(
        $ownerOutput |
            ForEach-Object { $_.ToString().Trim() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
    if ($ownerLines.Count -ne 1) {
        throw "Bench 原生卷所有权标记内容无效，拒绝复用：$BenchVolumeName。"
    }
    return $ownerLines[0]
}

function Get-DockerBackend {
    param(
        [Parameter(Mandatory = $true)][string]$WslDistro
    )

    $localDocker = Get-Command "docker" -ErrorAction SilentlyContinue
    if (
        $null -ne $localDocker -and
        (Test-NativeCommand `
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
    if (-not (Test-NativeCommand `
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

function Convert-ToDockerPath {
    param(
        [Parameter(Mandatory = $true)][string]$WindowsPath,
        [Parameter(Mandatory = $true)][hashtable]$DockerBackend
    )

    if ($DockerBackend.Name -eq "Windows") {
        return $WindowsPath.Replace("\", "/")
    }

    # wslpath 直接接收 C:\... 时会丢失反斜杠，必须先转成 C:/...。
    $normalizedWindowsPath = $WindowsPath.Replace("\", "/")
    $output = @(
        Invoke-NativeCommand `
            -Command $DockerBackend.Command `
            -Arguments @(
                "-d",
                $DockerBackend.WslDistro,
                "--",
                "wslpath",
                "-a",
                $normalizedWindowsPath
            ) `
            -FailureMessage "把 Windows 路径转换为 WSL 路径失败。" `
            -CaptureOutput
    )
    $convertedPath = ($output | Select-Object -Last 1).ToString().Trim()
    if ($convertedPath -notmatch "^/[^`r`n]*$") {
        throw "wslpath 返回了不合法路径：$convertedPath"
    }
    return $convertedPath
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$configuration = Read-AutoFlowConfiguration -ProjectRoot $projectRoot
$siteName = $configuration["AUTOFLOW_SITE"]
$adminPassword = $configuration["AUTOFLOW_ADMIN_PASSWORD"]
$wslDistro = $configuration["AUTOFLOW_WSL_DISTRO"]

if (
    [string]::IsNullOrWhiteSpace($siteName) -or
    $siteName -notmatch "^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+localhost$"
) {
    throw "AUTOFLOW_SITE 站点名不合法：只能使用小写字母、数字、连字符和点，并且必须以 .localhost 结尾。"
}
if ([string]::IsNullOrWhiteSpace($adminPassword)) {
    throw "缺少 AUTOFLOW_ADMIN_PASSWORD。请复制 deploy/env.example 为 .env 并设置本机管理员密码。"
}
if ($adminPassword -eq "change-me-locally") {
    throw "AUTOFLOW_ADMIN_PASSWORD 仍是示例值，请先在 .env 中修改。"
}
if ($adminPassword.Length -lt 12) {
    throw "AUTOFLOW_ADMIN_PASSWORD 至少需要 12 个字符。"
}
if ($wslDistro -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$") {
    throw "AUTOFLOW_WSL_DISTRO 不合法，只允许字母、数字、点、下划线和连字符。"
}

$upstreamLock = Read-UpstreamLock -ProjectRoot $projectRoot
$frappeDockerLock = $upstreamLock["frappe_docker"]
$containerImageLock = Read-ContainerImageLock -ProjectRoot $projectRoot
$frappeBenchImage = $containerImageLock["frappe_bench"]
$mariaDbImage = $containerImageLock["mariadb"]
$redisImage = $containerImageLock["redis"]
$runtimeRoot = Get-RuntimePath `
    -ProjectRoot $projectRoot `
    -ConfiguredPath $configuration["AUTOFLOW_RUNTIME"]
$runtimeParent = Split-Path -Parent $runtimeRoot

& (Join-Path $PSScriptRoot "check-environment.ps1") -WslDistro $wslDistro
$dockerBackend = Get-DockerBackend -WslDistro $wslDistro
$gitCommand = $null
$gitPrefix = @()
$runtimePathForGit = $runtimeRoot
if ($dockerBackend.Name -eq "WSL2") {
    $gitCommand = $dockerBackend.Command
    $gitPrefix = @("-d", $wslDistro, "--", "git")
    $runtimePathForGit = Convert-ToDockerPath `
        -WindowsPath $runtimeRoot `
        -DockerBackend $dockerBackend
}
else {
    $resolvedGit = Get-Command "git" -ErrorAction SilentlyContinue
    if ($null -eq $resolvedGit) {
        throw "找不到 Windows Git。"
    }
    $gitCommand = $resolvedGit.Source
}

if (-not (Test-Path -LiteralPath $runtimeRoot)) {
    New-Item -ItemType Directory -Force -Path $runtimeParent | Out-Null
    Invoke-NativeCommand `
        -Command $gitCommand `
        -Arguments (
            $gitPrefix +
            @(
                "clone",
                "--branch",
                $frappeDockerLock.Branch,
                $frappeDockerLock.Repository,
                $runtimePathForGit
            )
        ) `
        -FailureMessage "克隆 frappe_docker 失败。"
}
elseif (-not (Test-Path -LiteralPath (Join-Path $runtimeRoot ".git"))) {
    throw "运行目录已存在但不是 frappe_docker Git 仓库：$runtimeRoot"
}

$originOutput = @(
    Invoke-NativeCommand `
        -Command $gitCommand `
        -Arguments (
            $gitPrefix +
            @("-C", $runtimePathForGit, "remote", "get-url", "origin")
        ) `
        -FailureMessage "读取 frappe_docker 上游地址失败。" `
        -CaptureOutput
)
$origin = ($originOutput | Select-Object -Last 1).ToString().Trim()
if ($origin -notmatch "^https://github\.com/frappe/frappe_docker(?:\.git)?/?$") {
    throw "运行目录的 origin 不是官方 frappe_docker：$origin"
}

$trackedStatusOutput = @(
    Invoke-NativeCommand `
        -Command $gitCommand `
        -Arguments (
            $gitPrefix +
            @(
                "-C",
                $runtimePathForGit,
                "status",
                "--porcelain",
                "--untracked-files=no"
            )
        ) `
        -FailureMessage "检查 frappe_docker 工作树失败。" `
        -CaptureOutput
)
$trackedChanges = @(
    $trackedStatusOutput |
        ForEach-Object { $_.ToString().Trim() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
)
if ($trackedChanges.Count -gt 0) {
    throw "frappe_docker 存在未提交的受跟踪文件改动，拒绝覆盖。"
}

$frappeDockerCommit = $frappeDockerLock.Commit
$commitObject = "${frappeDockerCommit}^{commit}"
$commitExists = Test-NativeCommand `
    -Command $gitCommand `
    -Arguments ($gitPrefix + @("-C", $runtimePathForGit, "cat-file", "-e", $commitObject))
if (-not $commitExists) {
    $shallowOutput = @(
        Invoke-NativeCommand `
            -Command $gitCommand `
            -Arguments (
                $gitPrefix +
                @("-C", $runtimePathForGit, "rev-parse", "--is-shallow-repository")
            ) `
            -FailureMessage "检查 frappe_docker 仓库深度失败。" `
            -CaptureOutput
    )
    $isShallow = ($shallowOutput | Select-Object -Last 1).ToString().Trim() -eq "true"
    $fetchArguments = if ($isShallow) {
        @(
            "-C",
            $runtimePathForGit,
            "fetch",
            "--unshallow",
            "origin",
            $frappeDockerLock.Branch
        )
    }
    else {
        @(
            "-C",
            $runtimePathForGit,
            "fetch",
            "origin",
            $frappeDockerLock.Branch
        )
    }
    Invoke-NativeCommand `
        -Command $gitCommand `
        -Arguments ($gitPrefix + $fetchArguments) `
        -FailureMessage "获取锁定的 frappe_docker 提交失败。"
}
Invoke-NativeCommand `
    -Command $gitCommand `
    -Arguments (
        $gitPrefix +
        @("-C", $runtimePathForGit, "checkout", "--detach", $frappeDockerCommit)
    ) `
    -FailureMessage "切换到锁定的 frappe_docker 提交失败。"
$headOutput = @(
    Invoke-NativeCommand `
        -Command $gitCommand `
        -Arguments (
            $gitPrefix +
            @("-C", $runtimePathForGit, "rev-parse", "HEAD")
        ) `
        -FailureMessage "读取 frappe_docker 当前提交失败。" `
        -CaptureOutput
)
$actualFrappeDockerCommit = ($headOutput | Select-Object -Last 1).ToString().Trim()
if ($actualFrappeDockerCommit -ne $frappeDockerCommit) {
    throw "frappe_docker 提交校验失败：期望 $frappeDockerCommit，实际 $actualFrappeDockerCommit。"
}

$devcontainerSource = Join-Path $runtimeRoot "devcontainer-example"
$devcontainerTarget = Join-Path $runtimeRoot ".devcontainer"
if (-not (Test-Path -LiteralPath $devcontainerSource -PathType Container)) {
    throw "官方 frappe_docker 中缺少 devcontainer-example：$devcontainerSource"
}
if (Test-Path -LiteralPath $devcontainerTarget) {
    $actualTargetPath = [System.IO.Path]::GetFullPath($devcontainerTarget)
    $expectedTargetPath = [System.IO.Path]::GetFullPath(
        (Join-Path $runtimeRoot ".devcontainer")
    )
    if (-not $actualTargetPath.Equals(
        $expectedTargetPath,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "拒绝刷新意外的 devcontainer 目录：$actualTargetPath"
    }
    Remove-Item -Recurse -Force -LiteralPath $actualTargetPath
}
Copy-Item `
    -Recurse `
    -LiteralPath $devcontainerSource `
    -Destination $devcontainerTarget

$composeFile = Join-Path $devcontainerTarget "docker-compose.yml"
if (-not (Test-Path -LiteralPath $composeFile -PathType Leaf)) {
    throw "开发容器配置缺失：$composeFile"
}

$overrideFile = Join-Path $devcontainerTarget "compose.autoflow.yaml"
$projectRootForYaml = (
    Convert-ToDockerPath -WindowsPath $projectRoot -DockerBackend $dockerBackend
).Replace("'", "''")
$runtimeRootForYaml = (
    Convert-ToDockerPath -WindowsPath $runtimeRoot -DockerBackend $dockerBackend
).Replace("'", "''")
$overrideContent = @"
services:
  mariadb:
    image: '${mariaDbImage}'
  redis-cache:
    image: '${redisImage}'
  redis-queue:
    image: '${redisImage}'
  frappe:
    image: '${frappeBenchImage}'
    volumes:
      - '${projectRootForYaml}:/workspace/autoflow_360'
      - '${runtimeRootForYaml}:/workspace/frappe_docker'
      - autoflow-bench-data:/workspace/development
volumes:
  autoflow-bench-data:
    name: autoflow-360-bench-data
    external: true
"@
Set-Content -LiteralPath $overrideFile -Value $overrideContent -Encoding UTF8

$composeArguments = @(
    "compose",
    "-f",
    (Convert-ToDockerPath -WindowsPath $composeFile -DockerBackend $dockerBackend),
    "-f",
    (Convert-ToDockerPath -WindowsPath $overrideFile -DockerBackend $dockerBackend)
)
$benchVolumeName = "autoflow-360-bench-data"
$projectIdentitySource = $projectRoot.ToLowerInvariant()
$sha256 = [System.Security.Cryptography.SHA256]::Create()
try {
    $projectIdentityBytes = $sha256.ComputeHash(
        [System.Text.Encoding]::UTF8.GetBytes($projectIdentitySource)
    )
}
finally {
    $sha256.Dispose()
}
$projectIdentity = (
    [System.BitConverter]::ToString($projectIdentityBytes)
).Replace("-", "").ToLowerInvariant()
$volumeOwner = "autoflow-360:v1:$projectIdentity`:$siteName"
$volumeOwnerFile = "/target/.autoflow-volume-owner"
$volumeReadyFile = "/target/.autoflow-volume-ready"
$volumeOwnerSourcePath = Join-Path $devcontainerTarget "volume-owner.txt"
[System.IO.File]::WriteAllText(
    $volumeOwnerSourcePath,
    "$volumeOwner`n",
    [System.Text.UTF8Encoding]::new($false)
)
$volumeOwnerSourceForDocker = Convert-ToDockerPath `
    -WindowsPath $volumeOwnerSourcePath `
    -DockerBackend $dockerBackend
if ($volumeOwnerSourceForDocker.Contains(",")) {
    throw "卷所有权标记源路径包含 Docker --mount 不支持的逗号：$volumeOwnerSourceForDocker"
}
Invoke-NativeCommand `
    -Command $dockerBackend.Command `
    -Arguments (
        $dockerBackend.Prefix +
        @("volume", "create", $benchVolumeName)
    ) `
    -FailureMessage "创建 Bench 原生数据卷失败。"

$volumeReady = Test-NativeCommand `
    -Command $dockerBackend.Command `
    -Arguments (
        $dockerBackend.Prefix +
        @(
            "run",
            "--rm",
            "--mount",
            "type=volume,source=$benchVolumeName,target=/target",
            $frappeBenchImage,
            "test",
            "-f",
            $volumeReadyFile
        )
    )
$volumeOwnerExists = Test-NativeCommand `
    -Command $dockerBackend.Command `
    -Arguments (
        $dockerBackend.Prefix +
        @(
            "run",
            "--rm",
            "--mount",
            "type=volume,source=$benchVolumeName,target=/target",
            $frappeBenchImage,
            "test",
            "-f",
            $volumeOwnerFile
        )
    )
$writeVolumeOwnerArguments = @(
    "run",
    "--rm",
    "--user",
    "0:0",
    "--mount",
    "type=bind,source=$volumeOwnerSourceForDocker,target=/source/volume-owner,readonly",
    "--mount",
    "type=volume,source=$benchVolumeName,target=/target",
    $frappeBenchImage,
    "cp",
    "/source/volume-owner",
    $volumeOwnerFile
)
$touchVolumeReadyArguments = @(
    "run",
    "--rm",
    "--user",
    "0:0",
    "--mount",
    "type=volume,source=$benchVolumeName,target=/target",
    $frappeBenchImage,
    "touch",
    $volumeReadyFile
)
$actualVolumeOwner = $null
if ($volumeOwnerExists) {
    $actualVolumeOwner = Read-BenchVolumeOwner `
        -DockerBackend $dockerBackend `
        -BenchVolumeName $benchVolumeName `
        -FrappeBenchImage $frappeBenchImage `
        -VolumeOwnerFile $volumeOwnerFile
    if ($actualVolumeOwner -ne $volumeOwner) {
        throw (
            "Bench 原生卷属于其他项目或站点，拒绝复用：$benchVolumeName。"
        )
    }
}

$legacyDevelopmentPath = Join-Path $runtimeRoot "development"
$legacyBenchPath = Join-Path $legacyDevelopmentPath "frappe-bench"
$legacySiteConfig = Join-Path `
    $runtimeRoot `
    "development\frappe-bench\sites\$siteName\site_config.json"
$shouldValidateLegacyVolume = $false
$shouldCopyLegacyBench = $false
$shouldWriteVolumeOwner = $false
if (-not $volumeReady) {
    Invoke-NativeCommand `
        -Command $dockerBackend.Command `
        -Arguments (
            $dockerBackend.Prefix +
            $composeArguments +
            @("stop", "frappe")
        ) `
        -FailureMessage "停止旧 Frappe 容器失败。"

    if ($volumeOwnerExists) {
        # 所有权已在前面校验；补回 ready 标记即可，不复制或覆盖卷内数据。
        $shouldWriteVolumeOwner = $true
    }
    else {
        $volumeContentOutput = @(
            Invoke-NativeCommand `
                -Command $dockerBackend.Command `
                -Arguments (
                    $dockerBackend.Prefix +
                    @(
                        "run",
                        "--rm",
                        "--mount",
                        "type=volume,source=$benchVolumeName,target=/target",
                        $frappeBenchImage,
                        "sh",
                        "-c",
                        "find /target -mindepth 1 -maxdepth 1 ! -name .autoflow-volume-owner ! -name .autoflow-volume-ready -print -quit"
                    )
                ) `
                -FailureMessage "检查 Bench 原生卷内容失败。" `
                -CaptureOutput
        )
        $volumeHasUserContent = @(
            $volumeContentOutput |
                ForEach-Object { $_.ToString().Trim() } |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        ).Count -gt 0

        if ($volumeHasUserContent) {
            # 未标记的非空卷只能先确认来源，再重新覆盖复制以恢复中断迁移。
            $shouldValidateLegacyVolume = $true
            $shouldCopyLegacyBench = $true
        }
        elseif (Test-Path -LiteralPath $legacyBenchPath -PathType Container) {
            $shouldCopyLegacyBench = $true
        }
        $shouldWriteVolumeOwner = $true
    }
}
elseif (-not $volumeOwnerExists) {
    $shouldValidateLegacyVolume = $true
    $shouldWriteVolumeOwner = $true
}

if ($shouldValidateLegacyVolume) {
    if (-not (Test-Path -LiteralPath $legacySiteConfig -PathType Leaf)) {
        throw (
            "Bench 原生卷缺少所有权标记，且无法用旧站点配置验证来源；" +
            "拒绝复用同名卷：$benchVolumeName"
        )
    }
    $legacySiteHash = (
        Get-FileHash -LiteralPath $legacySiteConfig -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    $volumeSiteConfig = "/target/frappe-bench/sites/$siteName/site_config.json"
    $volumeHashOutput = @(
        Invoke-NativeCommand `
            -Command $dockerBackend.Command `
            -Arguments (
                $dockerBackend.Prefix +
                @(
                    "run",
                    "--rm",
                    "--mount",
                    "type=volume,source=$benchVolumeName,target=/target",
                    $frappeBenchImage,
                    "sha256sum",
                    $volumeSiteConfig
                )
            ) `
            -FailureMessage "验证旧 Bench 原生卷来源失败。" `
            -CaptureOutput
    )
    $volumeHashLines = @(
        $volumeHashOutput |
            ForEach-Object { $_.ToString().Trim() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
    if ($volumeHashLines.Count -ne 1) {
        throw "Bench 原生卷站点配置哈希输出无效，拒绝写入所有权标记。"
    }
    $volumeHashParts = @($volumeHashLines[0] -split "\s+")
    $volumeSiteHash = if ($volumeHashParts.Count -gt 0) {
        $volumeHashParts[0].ToLowerInvariant()
    }
    else {
        ""
    }
    if (
        $volumeSiteHash -notmatch "^[0-9a-f]{64}$" -or
        $volumeSiteHash -ne $legacySiteHash
    ) {
        throw "Bench 原生卷与当前项目旧站点配置不一致，拒绝写入所有权标记。"
    }
}

if ($shouldCopyLegacyBench) {
    if (-not (Test-Path -LiteralPath $legacyBenchPath -PathType Container)) {
        throw "缺少可用于恢复迁移的旧 Bench，拒绝覆盖非空原生卷。"
    }
    $developmentPathForDocker = Convert-ToDockerPath `
        -WindowsPath $legacyDevelopmentPath `
        -DockerBackend $dockerBackend
    if ($developmentPathForDocker.Contains(",")) {
        throw "旧 Bench 路径包含 Docker --mount 不支持的逗号：$developmentPathForDocker"
    }
    Write-Host "正在把旧 Bench 复制到 Docker 原生卷；源目录会保留为恢复备份。"
    Invoke-NativeCommand `
        -Command $dockerBackend.Command `
        -Arguments (
            $dockerBackend.Prefix +
            @(
                "run",
                "--rm",
                "--user",
                "0:0",
                "--mount",
                "type=bind,source=$developmentPathForDocker,target=/source,readonly",
                "--mount",
                "type=volume,source=$benchVolumeName,target=/target",
                $frappeBenchImage,
                "sh",
                "-c",
                "tar -C /source -cf - . | tar -C /target -xpf -"
            )
        ) `
        -FailureMessage "迁移旧 Bench 到 Docker 原生卷失败。"
}

if ($shouldWriteVolumeOwner) {
    Invoke-NativeCommand `
        -Command $dockerBackend.Command `
        -Arguments ($dockerBackend.Prefix + $writeVolumeOwnerArguments) `
        -FailureMessage "写入 Bench 原生卷所有权标记失败。"
    Invoke-NativeCommand `
        -Command $dockerBackend.Command `
        -Arguments ($dockerBackend.Prefix + $touchVolumeReadyArguments) `
        -FailureMessage "写入 Bench 原生卷就绪标记失败。"
    $verifiedVolumeOwner = Read-BenchVolumeOwner `
        -DockerBackend $dockerBackend `
        -BenchVolumeName $benchVolumeName `
        -FrappeBenchImage $frappeBenchImage `
        -VolumeOwnerFile $volumeOwnerFile
    if ($verifiedVolumeOwner -ne $volumeOwner) {
        throw "Bench 原生卷所有权标记写后校验失败：$benchVolumeName。"
    }
}
Invoke-NativeCommand `
    -Command $dockerBackend.Command `
    -Arguments ($dockerBackend.Prefix + $composeArguments + @("up", "-d")) `
    -FailureMessage "启动 Frappe 开发容器失败。"

$containerOutput = @(
    Invoke-NativeCommand `
        -Command $dockerBackend.Command `
        -Arguments ($dockerBackend.Prefix + $composeArguments + @("ps", "-q", "frappe")) `
        -FailureMessage "查询 Frappe 开发容器失败。" `
        -CaptureOutput
)
$frappeContainer = @(
    $containerOutput |
        ForEach-Object { $_.ToString().Trim() } |
        Where-Object { $_ -match "^[0-9a-f]{12,64}$" }
) | Select-Object -Last 1
if ([string]::IsNullOrWhiteSpace($frappeContainer)) {
    throw "找不到正在运行的 frappe 开发容器，请检查 docker compose 日志。"
}

Invoke-NativeCommand `
    -Command $dockerBackend.Command `
    -Arguments (
        $dockerBackend.Prefix +
        @(
            "exec",
            "--env",
            "AUTOFLOW_SITE=$siteName",
            "--env",
            "AUTOFLOW_ADMIN_PASSWORD=$adminPassword",
            $frappeContainer,
            "bash",
            "/workspace/autoflow_360/scripts/bootstrap-container.sh"
        )
    ) `
    -FailureMessage "初始化 AutoFlow 360 站点失败。"

Write-Host "开发环境初始化完成。" -ForegroundColor Green
Write-Host "先运行 .\scripts\bench.ps1 --site $siteName list-apps 验证应用，再运行 .\scripts\bench.ps1 start 启动服务。"
