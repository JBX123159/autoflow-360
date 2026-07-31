$ErrorActionPreference = "Stop"

function Read-SiteSetting {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot
    )

    $allowedKeys = @(
        "AUTOFLOW_SITE",
        "AUTOFLOW_ADMIN_PASSWORD",
        "AUTOFLOW_RUNTIME",
        "AUTOFLOW_WSL_DISTRO"
    )
    $siteName = "autoflow.localhost"
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
            if ($key -eq "AUTOFLOW_SITE") {
                $siteName = $value
            }
        }
    }

    $environmentSite = [Environment]::GetEnvironmentVariable("AUTOFLOW_SITE", "Process")
    if ($null -ne $environmentSite) {
        if (
            $environmentSite.IndexOf([char]0) -ge 0 -or
            $environmentSite.Contains("`r") -or
            $environmentSite.Contains("`n")
        ) {
            throw "环境变量 AUTOFLOW_SITE 包含换行或 NUL 字符。"
        }
        $siteName = $environmentSite
    }

    if (
        [string]::IsNullOrWhiteSpace($siteName) -or
        $siteName -notmatch "^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+localhost$"
    ) {
        throw "AUTOFLOW_SITE 站点名不合法：只能使用小写字母、数字、连字符和点，并且必须以 .localhost 结尾。"
    }
    return $siteName
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$siteName = Read-SiteSetting -ProjectRoot $projectRoot

try {
    & (Join-Path $PSScriptRoot "bench.ps1") `
        --site $siteName set-config allow_tests true
    & (Join-Path $PSScriptRoot "bench.ps1") `
        --site $siteName run-tests --app autoflow_360
}
catch {
    throw (
        "AutoFlow 360 测试失败：$($_.Exception.Message) " +
        "如果上方包含 Lock wait timeout exceeded，请先结束正在运行的 " +
        "bench.ps1 start 和残留测试进程，等待数据库事务释放后再重跑。"
    )
}

Write-Host "AutoFlow 360 测试通过。" -ForegroundColor Green
