# AutoFlow 360 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Frappe CRM 与 ERPNext 开源基座上，交付一套可测试、可部署、可演示的汽车零部件客户项目与供应链协同平台。

**Architecture:** Frappe Framework、ERPNext、Frappe CRM 与独立自定义应用 `autoflow_360` 安装在同一站点。标准销售、采购、库存和财务单据由 ERPNext 承载，汽车客户项目、样品、风险、异常、门户和 AI 能力由自定义应用实现，并通过公开钩子和链接字段集成。

**Tech Stack:** Frappe Framework v16、ERPNext v16、Frappe CRM v1 `main`、Python 3.14.x、Node.js 24+、MariaDB、Redis、Docker Engine 23+、Docker Compose v2、Frappe TestCase、Playwright、GitHub Actions。

## Global Constraints

- Frappe Framework 固定 `version-16`，ERPNext 固定 `version-16`，Frappe CRM 固定 `main` 稳定线。
- Python 固定为 3.14.x（即 `>=3.14,<3.15`），Node.js 最低主版本为 24，Docker Engine 最低版本为 23，必须使用 Compose v2。
- 自定义应用采用 `AGPL-3.0-only`，保留 ERPNext GPL-3.0 与 Frappe CRM AGPL-3.0 的来源和署名。
- 不直接修改 Frappe、ERPNext、Frappe CRM 或 frappe_docker 的上游核心源码。
- 所有业务写入必须通过服务端校验；前端限制不能作为唯一安全措施。
- 商机转项目、报价转订单、订单转需求、规则扫描和演示数据初始化必须幂等。
- AI 只能生成摘要、建议和草稿，不能提交或取消业务单据、改变库存、执行付款、关闭异常或绕过审批。
- 模型不可用时，客户项目、订单、采购、库存、财务、异常和确定性风险引擎必须继续工作。
- 演示数据全部为合成数据，不描述为真实企业经营结果。
- 默认不购买云服务、域名、数据库或模型额度；产生费用前必须另行确认。
- 每项业务实现遵循测试先行：先写失败测试，再实现最小可用逻辑，再运行相关测试。
- 每个任务结束后创建独立提交；提交前执行 `git diff --check` 和该任务列出的测试命令。

---

## 0. 文件结构与职责

```text
.
├─ autoflow_360/
│  ├─ __init__.py
│  ├─ hooks.py
│  ├─ modules.txt
│  ├─ patches.txt
│  ├─ install.py
│  ├─ api/
│  │  ├─ project.py
│  │  ├─ portal.py
│  │  └─ analytics.py
│  ├─ ai/
│  │  ├─ context_builder.py
│  │  ├─ schemas.py
│  │  ├─ service.py
│  │  ├─ audit.py
│  │  └─ providers/
│  │     ├─ base.py
│  │     ├─ disabled.py
│  │     └─ openai_compatible.py
│  ├─ permissions/
│  │  ├─ project.py
│  │  └─ portal.py
│  ├─ risk_engine/
│  │  ├─ types.py
│  │  ├─ rules.py
│  │  ├─ service.py
│  │  └─ scheduled.py
│  ├─ services/
│  │  ├─ idempotency.py
│  │  ├─ deal_conversion.py
│  │  ├─ sample_workflow.py
│  │  ├─ sales_conversion.py
│  │  ├─ material_planning.py
│  │  ├─ project_status.py
│  │  ├─ project_closure.py
│  │  └─ exception_workflow.py
│  ├─ setup/
│  │  ├─ custom_fields.py
│  │  ├─ roles.py
│  │  └─ workflows.py
│  ├─ autoflow_360/
│  │  ├─ doctype/
│  │  ├─ page/
│  │  └─ report/
│  ├─ public/
│  │  ├─ css/autoflow.css
│  │  └─ js/
│  ├─ templates/
│  └─ www/
├─ deploy/
│  ├─ apps.dev.json
│  ├─ apps.production.json
│  ├─ env.example
│  └─ oracle/
├─ scripts/
│  ├─ check-environment.ps1
│  ├─ bootstrap-dev.ps1
│  ├─ run-tests.ps1
│  ├─ seed-demo.ps1
│  └─ verify-backup.ps1
├─ tests/
│  ├─ static/
│  ├─ e2e/
│  └─ performance/
├─ docs/
│  ├─ architecture/
│  ├─ deployment/
│  ├─ user-guide/
│  ├─ test-report/
│  └─ interview/
├─ .github/workflows/
├─ pyproject.toml
├─ README.md
├─ NOTICE.md
└─ LICENSE
```

职责约束：

- `services/` 负责跨单据业务事务，不放页面渲染逻辑。
- `risk_engine/` 只负责确定性规则，不调用大模型。
- `ai/` 只读取当前用户有权访问的数据，关键业务写入仍由人工触发。
- `permissions/` 同时提供列表查询条件和单记录权限判断。
- DocType 控制器只做本对象校验，把跨对象事务委托给 `services/`。
- `tests/static/` 可在未安装 Frappe 时运行；业务测试必须在完整站点中运行。
- 计划中的 Frappe 命令统一通过 `scripts/bench.ps1` 从 Windows 调用；脚本负责进入开发容器和 Bench 目录。
- 每个 Python 包目录和 DocType 目录均创建空的 `__init__.py`；下文文件列表不重复列出这些机械文件。

### 0.1 测试数据工厂契约

Task 5 创建 `autoflow_360/tests/factories.py`，后续任务在同一文件中增加所需工厂。所有工厂使用 `_Test` 前缀、`.example.invalid` 邮箱或 `SYNTHETIC` 标记，返回已插入但仅在函数名明确写出 `submitted` 时才提交的 Frappe Document。工厂只负责准备测试前置条件，不绕过被测服务。

| 首次提供任务 | 函数签名 | 固定行为 |
| --- | --- | --- |
| 5 | `make_customer_project(title: str = "Synthetic Project", insert: bool = True, customer: str = "_Test Customer")` | 创建公司、客户、负责人和至少一名项目成员 |
| 6 | `make_crm_deal(title: str)` | 创建带组织、负责人、币种、预计金额和关闭日期的 CRM Deal |
| 7 | `make_sample_request(inspection_status: str = "待检验")` | 创建第一轮草稿样品；`make_dispatched_sample()` 创建已检验并发出的样品 |
| 8 | `make_project_quotation(sample_decision: str)` | 创建项目报价；`make_submitted_project_quotation()` 创建客户确认且已提交报价；`make_approval_request(requested_by: str)` 创建超权限请求 |
| 9 | `make_sales_order(item_code: str, quantity: float)` | 创建已提交项目销售订单；`set_warehouse_stock(item_code, warehouse, quantity)` 通过 Stock Reconciliation 建立库存 |
| 10 | `make_project_material_request()` | 创建已提交项目物料需求；其余采购工厂分别建立供应商门户用户、报价、订单、收货、采购发票和付款 |
| 11 | `make_delivery_note(quantity: float, available_stock: float)` | 创建未提交交货单；`make_submitted_delivery_note(customer="_Test Customer")` 创建已提交交货单 |
| 12 | `make_fulfilled_project(outstanding_amount: float)` | 建立销售、交付、发票和指定应收余额；余额为零时同时创建已通过的结项审批 |
| 13 | `make_overdue_project()` | 建立逾期节点；其余风险工厂分别建立供应商延期、未付款和已有风险 |
| 14 | `make_business_exception(project_name: str, risk_level: str, status: str)` | 创建带来源单据、责任人、根因和整改动作的合成异常 |
| 15 | `make_internal_user(email: str, roles: list[str])` | 创建内部用户；客户门户、项目成员、公司权限工厂建立精确授权关系 |
| 16 | `make_project_with_risk()` | 创建当前用户可读且至少带一个风险的项目 |

每个测试文件显式导入自己使用的工厂；若上游测试记录已经存在，工厂用稳定键复用，不重复创建。

---

### Task 1: 建立仓库契约、许可证和环境体检

**Files:**

- Create: `README.md`
- Create: `NOTICE.md`
- Create: `LICENSE`
- Create: `docs/research/upstream-baseline.md`
- Create: `scripts/check-environment.ps1`
- Create: `tests/__init__.py`
- Create: `tests/static/__init__.py`
- Create: `tests/static/test_repository_contract.py`
- Create: `tests/static/test_environment_check.py`
- Modify: `.gitignore`

**Interfaces:**

- Consumes: 已批准的 `Product-Spec.md` 与技术设计说明。
- Produces: `scripts/check-environment.ps1`，后续所有任务在启动环境前调用；明确的上游与个人贡献边界。

- [ ] **Step 1: 写仓库契约失败测试**

```python
# tests/static/test_repository_contract.py
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RepositoryContractTest(unittest.TestCase):
    def test_required_documents_exist(self):
        for relative_path in (
            "README.md",
            "NOTICE.md",
            "LICENSE",
            "Product-Spec.md",
            "docs/superpowers/specs/2026-07-29-autoflow-360-design.md",
        ):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_readme_states_upstream_and_custom_scope(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")
        for required_text in (
            "AutoFlow 360",
            "Frappe CRM",
            "ERPNext",
            "规划中的自主新增范围",
            "合成数据",
        ):
            self.assertIn(required_text, content)

    def test_unfinished_scope_is_labeled_as_planned(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("规划中的自主新增范围", readme)
        self.assertIn("计划自主实现，当前状态以实际代码和测试为准", readme)
        self.assertIn("规划中的自主新增范围", notice)

    def test_license_is_agpl(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", license_text)


if __name__ == "__main__":
    unittest.main()
```

`tests/static/test_environment_check.py` 仅使用 Python 标准库和临时假命令，不引入第三方测试库。测试先于脚本实现创建，并固定以下 13 个不可退化行为：

1. 支持版本的 Git、Docker、Compose 与 Ubuntu WSL2 全部通过。
2. Docker/Compose 缺失时列出 `Docker Engine` 与 `Docker Compose`。
3. Compose 命令不可用时给出明确版本检查错误。
4. Docker Compose v1 被拒绝。
5. Docker Compose 异常版本格式被拒绝。
6. Docker Engine 低于 23 被拒绝。
7. WSL 缺失时给出明确中文错误。
8. WSL 中没有 Ubuntu 时被拒绝。
9. Ubuntu 只有 WSL1 时被拒绝。
10. 带前导空格和星号的 Ubuntu WSL2 行可以解析。
11. 无星号的 Ubuntu WSL2 行可以解析。
12. 多发行版中存在至少一个 Ubuntu WSL2 时通过。
13. WSL 输出含 NUL 字符时由 `ConvertTo-CleanLines` 清洗后正确解析。

- [ ] **Step 2: 运行仓库与环境行为测试并确认失败原因**

Run:

```powershell
python -m unittest tests.static.test_repository_contract -v
python -m unittest tests.static.test_environment_check -v
```

Expected: 仓库测试因 `README.md`、`NOTICE.md` 或 `LICENSE` 缺失而失败；环境行为测试因 `scripts/check-environment.ps1` 尚未实现而失败。完成 Step 3 和 Step 4 后重新运行，两组测试必须全部通过。

- [ ] **Step 3: 创建许可证、来源说明和项目首页**

Run:

```powershell
Invoke-WebRequest `
  -Uri "https://www.gnu.org/licenses/agpl-3.0.txt" `
  -OutFile "LICENSE"
```

`NOTICE.md` 必须逐项列出：

```markdown
# Third-Party Notices

AutoFlow 360 是独立自定义应用，不是 Frappe、ERPNext 或 Frappe CRM 的官方产品。

| 项目 | 用途 | 来源 | 许可证 |
| --- | --- | --- | --- |
| Frappe Framework | 应用框架 | https://github.com/frappe/frappe | MIT |
| ERPNext | 销售、采购、库存、财务 | https://github.com/frappe/erpnext | GPL-3.0 |
| Frappe CRM | 线索、组织、联系人、商机 | https://github.com/frappe/crm | AGPL-3.0 |
| frappe_docker | 容器构建与部署参考 | https://github.com/frappe/frappe_docker | MIT |

本仓库规划中的自主新增范围包括客户项目、样品闭环、风险引擎、异常整改、
客户/供应商门户扩展、AI 分析审计、演示数据、自动化测试和求职交付材料。
以上内容计划自主实现，当前状态以实际代码和测试为准。
```

`README.md` 首屏必须包含项目一句话介绍、业务闭环图、三条演示路径、快速开始、测试命令、上游边界、合成数据声明和许可证；尚未完成的范围必须使用“规划中的自主新增范围”和“计划自主实现，当前状态以实际代码和测试为准”，不得写成完成态。

- [ ] **Step 4: 编写可直接执行的环境体检脚本**

```powershell
# scripts/check-environment.ps1
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

function Get-UbuntuWsl2Version {
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

    $ubuntuVersions = @()
    foreach ($line in $lines) {
        $normalized = [regex]::Replace($line, "^\s*\*?\s*", "")
        $columns = @($normalized -split "\s+")
        if ($columns.Count -lt 2) {
            continue
        }
        if ($columns[0] -match "^Ubuntu(?:-.+)?$") {
            $ubuntuVersions += $columns[$columns.Count - 1]
        }
    }

    if ($ubuntuVersions.Count -eq 0) {
        throw "WSL 中未安装 Ubuntu 发行版。请按 README.md 快速开始章节安装 Ubuntu WSL2。"
    }
    if ($ubuntuVersions -notcontains "2") {
        throw "Ubuntu 发行版必须使用 WSL2；当前 VERSION 为：$($ubuntuVersions -join '、')。"
    }
    return "VERSION 2"
}

$results = [ordered]@{
    git = Get-CommandVersion -Command "git" -Arguments @("--version") -DisplayName "Git"
    docker = Get-CommandVersion -Command "docker" -Arguments @("--version") -DisplayName "Docker Engine"
    compose = Get-CommandVersion -Command "docker" -Arguments @("compose", "version") -DisplayName "Docker Compose"
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

$ubuntuWslVersion = Get-UbuntuWsl2Version
Write-Host ("{0,-10} {1}" -f "ubuntu", $ubuntuWslVersion)
Write-Host "环境体检通过。" -ForegroundColor Green
```

该文件必须以 UTF-8 BOM 保存，确保 Windows PowerShell 5.1 能正确解析中文错误信息。脚本行为以 `tests/static/test_environment_check.py` 的 13 项测试为准；修改后不得降低 Compose v2、Ubuntu WSL2、星号/多发行版和 NUL 清洗契约。

`.gitignore` 增加：

```gitignore
.runtime/
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
node_modules/
sites/
logs/
*.log
playwright-report/
test-results/
```

- [ ] **Step 5: 运行静态测试和格式检查**

Run:

```powershell
python -m unittest discover -s tests/static -v
git diff --check
```

Expected: 全部测试显示 `OK`，`git diff --check` 无输出。

- [ ] **Step 6: 提交仓库契约**

```powershell
git add README.md NOTICE.md LICENSE docs/research/upstream-baseline.md scripts/check-environment.ps1 tests/__init__.py tests/static/__init__.py tests/static/test_repository_contract.py tests/static/test_environment_check.py .gitignore
git commit -m "docs: establish repository and upstream contract"
```

- [ ] **Step 7: 创建免费的公开 GitHub 仓库并建立远端**

Run:

```powershell
gh auth status
if ($LASTEXITCODE -ne 0) {
    gh auth login --hostname github.com --web --git-protocol https
}
if (-not (gh repo view JBX123159/autoflow-360 2>$null)) {
    gh repo create JBX123159/autoflow-360 `
      --public `
      --description "Automotive customer project and supply-chain collaboration platform"
}
if (-not (git remote get-url origin 2>$null)) {
    git remote add origin https://github.com/JBX123159/autoflow-360.git
}
git push origin HEAD:main
git push -u origin codex/autoflow-360
gh repo edit JBX123159/autoflow-360 --default-branch main
```

Expected: 公开仓库存在，默认分支为 `main`，开发分支为 `codex/autoflow-360`。创建前必须在执行界面向用户重述仓库名称、公开可见性和推送分支。

---

### Task 2: 初始化 Frappe 自定义应用包

**Files:**

- Create: `pyproject.toml`
- Create: `autoflow_360/__init__.py`
- Create: `autoflow_360/hooks.py`
- Create: `autoflow_360/modules.txt`
- Create: `autoflow_360/patches.txt`
- Create: `autoflow_360/config/__init__.py`
- Create: `autoflow_360/config/desktop.py`
- Create: `autoflow_360/public/images/autoflow-360-logo.svg`
- Create: `autoflow_360/autoflow_360/__init__.py`
- Create: `autoflow_360/api/__init__.py`
- Create: `autoflow_360/ai/__init__.py`
- Create: `autoflow_360/ai/providers/__init__.py`
- Create: `autoflow_360/permissions/__init__.py`
- Create: `autoflow_360/risk_engine/__init__.py`
- Create: `autoflow_360/services/__init__.py`
- Create: `autoflow_360/setup/__init__.py`
- Create: `autoflow_360/tests/__init__.py`
- Create: `tests/static/test_app_metadata.py`
- Create: `tests/build/__init__.py`
- Create: `tests/build/test_wheel_metadata.py`

**Interfaces:**

- Consumes: Python 3.14.x 与 Frappe v16 应用目录约定。
- Produces: 可被 Bench 安装的包 `autoflow_360`；后续任务依赖 `hooks.py`，安装钩子在 Task 4 增加。

- [ ] **Step 1: 写元数据失败测试**

```python
# tests/static/test_app_metadata.py
from pathlib import Path
import ast
import tomllib
import unittest
import xml.etree.ElementTree as ElementTree

ROOT = Path(__file__).resolve().parents[2]


class AppMetadataTest(unittest.TestCase):
    def test_pyproject_contract(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = data["project"]
        self.assertEqual(project["name"], "autoflow-360")
        self.assertEqual(project["requires-python"], ">=3.14,<3.15")
        self.assertEqual(data["tool"]["bench"]["frappe-dependencies"]["frappe"], ">=16.0.0,<17.0.0")

    def test_hooks_are_valid_python(self):
        hooks_path = ROOT / "autoflow_360" / "hooks.py"
        tree = ast.parse(hooks_path.read_text(encoding="utf-8"))
        assignments = {
            target.id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and target.id in {"app_license", "required_apps", "add_to_apps_screen"}
        }
        self.assertEqual(assignments["app_license"], "AGPL-3.0-only")
        self.assertEqual(assignments["required_apps"], ["erpnext", "crm"])
        self.assertEqual(
            assignments["add_to_apps_screen"],
            [
                {
                    "name": "autoflow_360",
                    "logo": "/assets/autoflow_360/images/autoflow-360-logo.svg",
                    "title": "AutoFlow 360",
                    "route": "/desk",
                }
            ],
        )

        logo_path = (
            ROOT
            / "autoflow_360"
            / "public"
            / "images"
            / "autoflow-360-logo.svg"
        )
        self.assertTrue(logo_path.is_file())
        root_element = ElementTree.parse(logo_path).getroot()
        self.assertEqual(root_element.tag, "{http://www.w3.org/2000/svg}svg")

    def test_module_name_is_stable(self):
        modules = (ROOT / "autoflow_360" / "modules.txt").read_text(encoding="utf-8")
        self.assertEqual(modules.strip(), "AutoFlow 360")


if __name__ == "__main__":
    unittest.main()
```

`tests/build/test_wheel_metadata.py` 必须与离线静态测试分离，使用标准库 `subprocess` 在自动清理的临时目录中执行 `python -m pip wheel . --no-deps`。测试打开真实 wheel，确认包含 `autoflow_360/hooks.py`、`autoflow_360/public/images/autoflow-360-logo.svg` 和 `LICENSE`，并精确校验 METADATA 中的 `Name`、`Version`、`Requires-Python`、`License-Expression` 与 `License-File`；构建失败信息同时输出 stdout 和 stderr。超时诊断必须包含 timeout 值、stdout 和 stderr，兼容进程输出为 `None`、字节串或字符串，并通过异常链保留原始 `TimeoutExpired` 上下文。

- [ ] **Step 2: 运行测试并确认包尚未存在**

Run:

```powershell
python -m unittest tests.static.test_app_metadata -v
```

Expected: `pyproject.toml` 或应用目录缺失。

- [ ] **Step 3: 创建最小可安装包**

```toml
# pyproject.toml
[project]
name = "autoflow-360"
authors = [
    { name = "JBX123159", email = "294367704+JBX123159@users.noreply.github.com" }
]
description = "Automotive customer project and supply-chain collaboration platform"
requires-python = ">=3.14,<3.15"
readme = "README.md"
license = "AGPL-3.0-only"
dynamic = ["version"]
dependencies = []

[build-system]
requires = ["flit_core >=3.11,<4"]
build-backend = "flit_core.buildapi"

[tool.flit.module]
name = "autoflow_360"

[tool.bench.frappe-dependencies]
frappe = ">=16.0.0,<17.0.0"

[tool.ruff]
line-length = 110
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "RUF"]

[tool.ruff.format]
quote-style = "double"
indent-style = "tab"
```

```python
# autoflow_360/__init__.py
__version__ = "0.1.0"
```

```python
# autoflow_360/hooks.py
from . import __version__ as app_version

app_name = "autoflow_360"
app_title = "AutoFlow 360"
app_publisher = "JBX123159"
app_description = "汽车零部件客户项目与供应链协同智能平台"
app_email = "294367704+JBX123159@users.noreply.github.com"
app_license = "AGPL-3.0-only"
required_apps = ["erpnext", "crm"]

add_to_apps_screen = [
	{
		"name": "autoflow_360",
		"logo": "/assets/autoflow_360/images/autoflow-360-logo.svg",
		"title": "AutoFlow 360",
		"route": "/desk",
	}
]

export_python_type_annotations = True
require_type_annotated_api_methods = True
```

`autoflow_360/modules.txt` 内容为：

```text
AutoFlow 360
```

`autoflow_360/patches.txt` 保持只有注释：

```text
[pre_model_sync]

[post_model_sync]
```

- [ ] **Step 4: 创建 Frappe v16 应用入口和兼容桌面元数据**

`add_to_apps_screen` 是 Frappe v16 应用页入口，当前指向真实可访问的 `/desk`；Task 17 创建专属工作台后再切换路由。Logo 使用仓库内原创 SVG，不加载字体、图片或其他外部资源。`config/desktop.py` 只保留为兼容元数据，不能作为 v16 唯一入口。

```python
# autoflow_360/config/desktop.py
from frappe import _


def get_data() -> list[dict]:
	return [
		{
			"module_name": "AutoFlow 360",
			"type": "module",
			"label": _("AutoFlow 360"),
			"color": "#1D4ED8",
			"icon": "octicon octicon-workflow",
		}
	]
```

- [ ] **Step 5: 运行静态测试**

Run:

```powershell
python -m unittest tests.static.test_app_metadata -v
python -m unittest discover -s tests/static -v
python -m unittest tests.build.test_wheel_metadata -v
python -m compileall -q autoflow_360
git diff --check
```

Expected: 静态测试与独立构建测试全部通过且无 Python 语法错误；真实 wheel 包含 `hooks.py`、应用 Logo 与 `LICENSE`，METADATA 中的名称、版本、Python 范围、许可证表达式和许可证文件均与 `pyproject.toml` 一致。构建测试使用临时目录并自动清理，不加入离线静态测试发现目录。

- [ ] **Step 6: 提交应用骨架**

```powershell
git add pyproject.toml autoflow_360 tests/static/test_app_metadata.py tests/build docs/superpowers/plans/2026-07-29-autoflow-360-implementation.md
git commit -m "feat: scaffold AutoFlow 360 Frappe app"
```

---

### Task 3: 建立可复现的本地 Frappe v16 环境

**Files:**

- Create: `deploy/apps.dev.json`
- Create: `deploy/container-lock.json`
- Create: `deploy/env.example`
- Create: `deploy/upstream-lock.json`
- Create: `.gitattributes`
- Create: `scripts/bootstrap-dev.ps1`
- Create: `scripts/bootstrap-container.sh`
- Create: `scripts/bench.ps1`
- Create: `scripts/run-tests.ps1`
- Create: `autoflow_360/development.py`
- Create: `docs/deployment/local-development.md`
- Create: `tests/static/test_deployment_contract.py`
- Modify: `README.md`
- Modify: `docs/research/upstream-baseline.md`
- Modify: `scripts/check-environment.ps1`
- Modify: `tests/static/test_environment_check.py`

**Interfaces:**

- Consumes: `scripts/check-environment.ps1`、Windows Docker 或 WSL2 Ubuntu 内的 Docker/Git、官方 `frappe_docker` 开发容器、当前仓库绝对路径。
- Produces: `deploy/upstream-lock.json`、Docker 原生卷 `autoflow-360-bench-data`、站点 `autoflow.localhost`、已安装并校验精确提交的 `frappe`、`erpnext`、`crm` 与 `autoflow_360`。

**当前官方契约修正（2026-07-30 核验 `frappe_docker/main`）：**

- 官方 `devcontainer-example/docker-compose.yml` 与 `development/installer.py` 的本地 MariaDB root 密码固定为 `123`。该口令仅限本机隔离开发，生产环境禁止复用此开发 Compose 或固定口令。
- 不提供实际无效的数据库 root 密码环境变量。管理员密码必须从 `.env` 或当前进程环境变量读取，再通过 `docker exec --env` 传入容器，不得硬编码。
- `.env` 只允许 `AUTOFLOW_SITE`、`AUTOFLOW_ADMIN_PASSWORD`、`AUTOFLOW_RUNTIME`、`AUTOFLOW_WSL_DISTRO` 四个允许名单键；拒绝重复项、未知项、错误格式、换行和 NUL，不使用 `Invoke-Expression`。
- 站点名只允许小写字母、数字、连字符和点，并且必须以 `.localhost` 结尾；运行目录必须位于当前仓库内。
- Windows Docker 可用时优先使用；否则安全调用指定 WSL2 Ubuntu 内的 Docker 与 Git，不依赖 Docker Desktop。Windows 路径必须先把反斜杠转换为正斜杠，再作为独立参数交给 `wslpath -a`，以支持中文和空格路径。
- Frappe/ERPNext 固定为 `version-16`，CRM 固定为 `main`，Python 3.14.x，Node 24。
- 首次真实部署成功后，四项不可变提交基线必须由实际仓库的 `git rev-parse HEAD` 回填；当前基线已于 2026-07-30 完成回填到文档和 `deploy/upstream-lock.json`。启动脚本必须检出并复核这些精确提交，分支名只用于首次安装和缺失对象的获取，不能充当版本锁。
- 干净安装必须先把锁定提交获取到本地缓存并建立 `autoflow-lock` 分支，再把本地路径交给官方安装器；不能先执行移动分支 HEAD 的安装代码后再回退。
- `frappe_docker/.devcontainer` 属于生成目录，每次初始化应从锁定提交的 `devcontainer-example` 刷新；上游仓库存在受跟踪文件改动时拒绝覆盖。首次建站使用一次性随机密码，真实本地密码由仅限 `.localhost` 和 `developer_mode` 的内部方法从进程环境同步，不能出现在 Bench 命令参数或日志中；已有站点每次初始化都同步为 `.env` 当前值并注销旧会话。
- Bench、虚拟环境、依赖与站点文件使用 Docker 原生卷 `autoflow-360-bench-data`，避免在 OneDrive/Windows 9P 挂载上执行高频小文件操作；检测到旧路径时先停止 Frappe 服务、复制到原生卷并保留旧目录作恢复备份。
- 容器镜像使用 `deploy/container-lock.json` 的 `sha256` 摘要；原生卷保存项目路径哈希、站点名和格式版本组成的所有权标记，冲突时拒绝复用。基础 Bench 不完整时明确停止并要求先备份，不自动覆盖未知数据。
- 2026-07-31 已完成真实卷来源哈希核验、错误旧标记修复和连续两次初始化；owner/ready、固定镜像、原生卷挂载、四个应用版本及 8 项真实 Frappe 测试均通过。

- [x] **Step 1: 写部署配置失败测试**

```python
# tests/static/test_deployment_contract.py
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DeploymentContractTest(unittest.TestCase):
    def test_dev_apps_are_pinned_to_compatible_branches(self):
        apps = json.loads((ROOT / "deploy" / "apps.dev.json").read_text(encoding="utf-8"))
        pairs = {(item["url"], item["branch"]) for item in apps}
        self.assertIn(("https://github.com/frappe/erpnext", "version-16"), pairs)
        self.assertIn(("https://github.com/frappe/crm", "main"), pairs)

    def test_example_environment_contains_no_real_secret(self):
        content = (ROOT / "deploy" / "env.example").read_text(encoding="utf-8")
        self.assertIn("AUTOFLOW_SITE=autoflow.localhost", content)
        self.assertIn("AUTOFLOW_ADMIN_PASSWORD=change-me-locally", content)
        self.assertNotIn("294367704", content)

    def test_upstream_baseline_has_four_immutable_revisions_and_date(self):
        content = (ROOT / "docs/research/upstream-baseline.md").read_text(encoding="utf-8")
        expected_projects = {
            "Frappe Framework",
            "ERPNext",
            "Frappe CRM",
            "frappe_docker",
        }
        rows = {}
        for line in content.splitlines():
            if not line.lstrip().startswith("|"):
                continue
            columns = [column.strip() for column in line.strip().strip("|").split("|")]
            if columns and columns[0] in expected_projects:
                self.assertNotIn(columns[0], rows, f"重复上游行：{columns[0]}")
                rows[columns[0]] = columns

        self.assertEqual(set(rows), expected_projects)
        for project, columns in rows.items():
            self.assertGreaterEqual(len(columns), 5, project)
            revisions = re.findall(r"`([0-9a-f]{40})`", columns[4])
            self.assertEqual(len(revisions), 1, project)

        dates = re.findall(r"获取日期：(\d{4}-\d{2}-\d{2})", content)
        self.assertGreaterEqual(len(dates), 1)
        self.assertEqual(len(set(dates)), 1)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: 运行测试并确认配置缺失**

Run:

```powershell
python -m unittest tests.static.test_deployment_contract -v
```

Expected: `deploy/apps.dev.json` 缺失。

- [x] **Step 3: 固定上游开发分支、精确提交和本地配置**

```json
[
  {
    "url": "https://github.com/frappe/erpnext",
    "branch": "version-16"
  },
  {
    "url": "https://github.com/frappe/crm",
    "branch": "main"
  }
]
```

```dotenv
# deploy/env.example
AUTOFLOW_SITE=autoflow.localhost
AUTOFLOW_ADMIN_PASSWORD=change-me-locally
AUTOFLOW_RUNTIME=.runtime/frappe_docker
AUTOFLOW_WSL_DISTRO=Ubuntu
```

`deploy/apps.dev.json` 为官方安装器提供兼容分支；`deploy/upstream-lock.json` 另外保存 `frappe_docker`、`frappe`、`erpnext`、`crm` 的官方仓库地址、兼容分支和 40 位提交哈希。后者是机器可读的不可变版本来源。

- [x] **Step 4: 编写幂等启动脚本**

`scripts/bootstrap-dev.ps1` 必须按以下顺序执行并在每步检查 `$LASTEXITCODE`：

```powershell
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$configuration = Read-AutoFlowConfiguration -ProjectRoot $projectRoot
$runtimeRoot = Get-RuntimePath -ProjectRoot $projectRoot -ConfiguredPath $configuration["AUTOFLOW_RUNTIME"]
$runtimeParent = Split-Path $runtimeRoot -Parent
$siteName = $configuration["AUTOFLOW_SITE"]
$adminPassword = $configuration["AUTOFLOW_ADMIN_PASSWORD"]
$wslDistro = $configuration["AUTOFLOW_WSL_DISTRO"]

& (Join-Path $PSScriptRoot "check-environment.ps1") -WslDistro $wslDistro
$dockerBackend = Get-DockerBackend -WslDistro $wslDistro

# WSL 后端使用同一发行版内的 Git，并把运行目录转换为 WSL 路径；
# Windows 后端使用 Windows Git。所有参数都以数组传递。
$gitCommand, $gitPrefix, $runtimePathForGit = Get-GitBackendArguments `
    -DockerBackend $dockerBackend `
    -WindowsRuntimePath $runtimeRoot
if (-not (Test-Path -LiteralPath $runtimeRoot)) {
    New-Item -ItemType Directory -Force -Path $runtimeParent | Out-Null
    Invoke-NativeCommand `
        -Command $gitCommand `
        -Arguments (
            $gitPrefix +
            @(
                "clone", "--branch", $frappeDockerLock.Branch,
                $frappeDockerLock.Repository, $runtimePathForGit
            )
        ) `
        -FailureMessage "克隆 frappe_docker 失败。"
}

# 读取 deploy/upstream-lock.json 后检出并校验锁定提交。
Invoke-NativeCommand `
    -Command $gitCommand `
    -Arguments (
        $gitPrefix +
        @("-C", $runtimePathForGit, "checkout", "--detach", $frappeDockerLock.Commit)
    ) `
    -FailureMessage "切换到锁定的 frappe_docker 提交失败。"

$devcontainerSource = Join-Path $runtimeRoot "devcontainer-example"
$devcontainerTarget = Join-Path $runtimeRoot ".devcontainer"
if (-not (Test-Path $devcontainerTarget)) {
    Copy-Item -Recurse -LiteralPath $devcontainerSource -Destination $devcontainerTarget
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
  frappe:
    volumes:
      - '${projectRootForYaml}:/workspace/autoflow_360'
      - '${runtimeRootForYaml}:/workspace/frappe_docker'
"@
Set-Content -LiteralPath $overrideFile -Value $overrideContent -Encoding UTF8

$composeArguments = @(
    "compose",
    "-f", (Convert-ToDockerPath -WindowsPath $composeFile -DockerBackend $dockerBackend),
    "-f", (Convert-ToDockerPath -WindowsPath $overrideFile -DockerBackend $dockerBackend)
)
Invoke-NativeCommand `
    -Command $dockerBackend.Command `
    -Arguments ($dockerBackend.Prefix + $composeArguments + @("up", "-d")) `
    -FailureMessage "启动 Frappe 开发容器失败。"

$frappeContainer = Get-FrappeContainer `
    -DockerBackend $dockerBackend `
    -ComposeArguments $composeArguments
if ([string]::IsNullOrWhiteSpace($frappeContainer)) {
    throw "找不到 frappe 开发容器。"
}

Invoke-NativeCommand `
    -Command $dockerBackend.Command `
    -Arguments (
        $dockerBackend.Prefix +
        @(
            "exec",
            "--env", "AUTOFLOW_SITE=$siteName",
            "--env", "AUTOFLOW_ADMIN_PASSWORD=$adminPassword",
            $frappeContainer,
            "bash",
            "/workspace/autoflow_360/scripts/bootstrap-container.sh"
        )
    ) `
    -FailureMessage "初始化 AutoFlow 360 站点失败。"

Write-Host "开发环境初始化完成；运行 scripts/bench.ps1 start 后访问 http://$siteName`:8000。" -ForegroundColor Green
```

容器内逻辑单独保存为 `scripts/bootstrap-container.sh`，并由 `.gitattributes` 强制使用 LF 换行。不得把多行 Bash 作为 `wsl.exe` 的单个命令字符串传递。脚本必须先从官方仓库取得锁定提交，在本地缓存创建 `autoflow-lock` 分支，再通过官方安装器的 `--frappe-repo` 和运行时 apps JSON 从本地锁定源码建 Bench/站点；完成后恢复官方 origin 并再次验证提交。锁定提交发生变化时重装 Python/Node 依赖和重建前端资源。脚本在登记 `autoflow_360` 前还必须检查 `sites/apps.txt` 是否以换行结尾，避免把应用名与上一行拼接；随后再执行 editable 安装、`install-app`、`migrate`、管理员密码同步与 `enable-scheduler`。

实现时必须向 devcontainer compose 增加两个只在本机生效的挂载：

```yaml
services:
  frappe:
    volumes:
      - '<经 wslpath 或 Windows 路径转换后的仓库绝对路径>:/workspace/autoflow_360'
      - '<经 wslpath 或 Windows 路径转换后的运行目录绝对路径>:/workspace/frappe_docker'
```

该覆盖文件保存为 `.runtime/frappe_docker/.devcontainer/compose.autoflow.yaml`，由脚本生成但不提交，主仓库只提交生成逻辑。

- [x] **Step 5: 编写统一 Bench 和测试入口**

```powershell
# scripts/bench.ps1
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composeRoot = Join-Path $projectRoot ".runtime\frappe_docker\.devcontainer"
$composeFile = Join-Path $composeRoot "docker-compose.yml"
$overrideFile = Join-Path $composeRoot "compose.autoflow.yaml"
if (-not (Test-Path $composeFile) -or -not (Test-Path $overrideFile)) {
    throw "开发环境未初始化，请先运行 scripts/bootstrap-dev.ps1。"
}

$dockerBackend = Get-DockerBackend -WslDistro $wslDistro
$composeFileForDocker = Convert-ToDockerPath -WindowsPath $composeFile -DockerBackend $dockerBackend
$overrideFileForDocker = Convert-ToDockerPath -WindowsPath $overrideFile -DockerBackend $dockerBackend
$frappeContainer = Get-FrappeContainer `
    -DockerBackend $dockerBackend `
    -ComposeArguments @("compose", "-f", $composeFileForDocker, "-f", $overrideFileForDocker)
if ([string]::IsNullOrWhiteSpace($frappeContainer)) {
    throw "Frappe 容器未运行，请重新执行 scripts/bootstrap-dev.ps1。"
}

Invoke-DockerCommand `
    -DockerBackend $dockerBackend `
    -Arguments @(
        "exec", "--workdir", "/workspace/development/frappe-bench",
        $frappeContainer, "bench"
    ) `
    -RemainingArguments $args
if ($LASTEXITCODE -ne 0) {
    throw "Bench 命令执行失败，退出码：$LASTEXITCODE。"
}
```

```powershell
# scripts/run-tests.ps1
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$siteName = Read-SiteSetting -ProjectRoot $projectRoot
& (Join-Path $PSScriptRoot "bench.ps1") `
    --site $siteName set-config allow_tests true
& (Join-Path $PSScriptRoot "bench.ps1") `
    --site $siteName run-tests --app autoflow_360
if ($LASTEXITCODE -ne 0) {
    throw "AutoFlow 360 测试失败。"
}
```

- [x] **Step 6: 启动环境并验证应用安装**

Run:

```powershell
Copy-Item deploy/env.example .env
# 编辑 .env，把 AUTOFLOW_ADMIN_PASSWORD 改为本机专用密码。
.\scripts\bootstrap-dev.ps1
.\scripts\bench.ps1 --site autoflow.localhost list-apps
```

Expected: 输出包含 `frappe`、`erpnext`、`crm` 和 `autoflow_360`。

- [x] **Step 7: 回填不可变的上游提交基线**

首次成功拉取并安装后，分别在以下仓库执行 `git rev-parse HEAD`：

- `.runtime/frappe_docker`
- `.runtime/frappe_docker/development/frappe-bench/apps/frappe`
- `.runtime/frappe_docker/development/frappe-bench/apps/erpnext`
- `.runtime/frappe_docker/development/frappe-bench/apps/crm`

把得到的四个 40 位提交哈希同时写入 `docs/research/upstream-baseline.md` 对应表格和 `deploy/upstream-lock.json`，文档写入统一的 `获取日期：YYYY-MM-DD`。启动脚本必须真实检出并验证锁文件中的提交；不得只记录哈希却继续使用移动分支 HEAD。完成后运行：

```powershell
python -m unittest tests.static.test_deployment_contract -v
```

Expected: 四个上游项目均有不可变提交证据和获取日期。

- [x] **Step 8: 提交开发环境**

```powershell
git add .gitattributes deploy autoflow_360/development.py autoflow_360/tests scripts/bootstrap-dev.ps1 scripts/bootstrap-container.sh scripts/bench.ps1 scripts/run-tests.ps1 scripts/check-environment.ps1 README.md docs/deployment/local-development.md docs/research/upstream-baseline.md tests/static/test_deployment_contract.py tests/static/test_environment_check.py
git commit -m "build: add reproducible Frappe v16 development environment"
```

---

### Task 4: 建立系统设置、角色和标准单据关联字段

**Files:**

- Create: `autoflow_360/setup/custom_fields.py`
- Create: `autoflow_360/setup/roles.py`
- Create: `autoflow_360/install.py`
- Create: `autoflow_360/autoflow_360/doctype/autoflow_settings/autoflow_settings.json`
- Create: `autoflow_360/autoflow_360/doctype/autoflow_settings/autoflow_settings.py`
- Create: `autoflow_360/autoflow_360/doctype/autoflow_settings/test_autoflow_settings.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: ERPNext 标准 DocType 与 Frappe 安装/迁移钩子。
- Produces: 七个内部角色、两个门户角色、单例设置对象、标准单据字段 `custom_customer_project`。

- [x] **Step 1: 写安装契约失败测试**

```python
from frappe.tests.utils import FrappeTestCase
import frappe


class TestAutoFlowSettings(FrappeTestCase):
	def test_required_roles_and_custom_fields_exist(self):
		for role in (
			"AutoFlow Sales Operations",
			"AutoFlow Project Manager",
			"AutoFlow Procurement",
			"AutoFlow Warehouse",
			"AutoFlow Finance",
			"AutoFlow Executive",
			"AutoFlow Administrator",
			"AutoFlow Customer Portal",
			"AutoFlow Supplier Portal",
		):
			self.assertTrue(frappe.db.exists("Role", role), role)

		for doctype in (
			"Quotation",
			"Sales Order",
			"Delivery Note",
			"Sales Invoice",
			"Material Request",
			"Request for Quotation",
			"Supplier Quotation",
			"Purchase Order",
			"Purchase Receipt",
			"Purchase Invoice",
			"Payment Entry",
		):
			self.assertTrue(frappe.get_meta(doctype).has_field("custom_customer_project"), doctype)
```

- [x] **Step 2: 运行测试并确认角色或字段缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --doctype "AutoFlow Settings"
```

Expected: 至少一个角色或 `custom_customer_project` 字段不存在。

- [x] **Step 3: 实现角色和字段的幂等安装**

```python
# autoflow_360/setup/roles.py
import frappe

ROLES = (
	"AutoFlow Sales Operations",
	"AutoFlow Project Manager",
	"AutoFlow Procurement",
	"AutoFlow Warehouse",
	"AutoFlow Finance",
	"AutoFlow Executive",
	"AutoFlow Administrator",
	"AutoFlow Customer Portal",
	"AutoFlow Supplier Portal",
)


def ensure_roles() -> None:
	for role_name in ROLES:
		if not frappe.db.exists("Role", role_name):
			frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)
```

```python
# autoflow_360/setup/custom_fields.py
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

PROJECT_LINK_DOCTYPES = (
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"Material Request",
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Payment Entry",
)


def ensure_custom_fields() -> None:
	fields = {
		doctype: [
			{
				"fieldname": "custom_customer_project",
				"label": "Customer Project",
				"fieldtype": "Link",
				"options": "Customer Project",
				"insert_after": "company",
				"module": "AutoFlow 360",
				"in_standard_filter": 1,
				"no_copy": 1,
			}
		]
		for doctype in PROJECT_LINK_DOCTYPES
	}
	create_custom_fields(fields, update=True)
```

```python
# autoflow_360/install.py
def after_install() -> None:
	from autoflow_360.setup.custom_fields import ensure_custom_fields
	from autoflow_360.setup.roles import ensure_roles

	ensure_roles()
	ensure_custom_fields()


def after_migrate() -> None:
	after_install()
```

`hooks.py` 增加：

```python
after_install = "autoflow_360.install.after_install"
after_migrate = "autoflow_360.install.after_migrate"
```

- [x] **Step 4: 创建单例设置**

设置字段必须包括：

```json
{
  "doctype": "DocType",
  "name": "AutoFlow Settings",
  "module": "AutoFlow 360",
  "issingle": 1,
  "fields": [
    {"fieldname": "feedback_warning_days", "label": "Feedback Warning Days", "fieldtype": "Int", "default": "3", "reqd": 1},
    {"fieldname": "quotation_expiry_warning_days", "label": "Quotation Expiry Warning Days", "fieldtype": "Int", "default": "7", "reqd": 1},
    {"fieldname": "project_inactive_days", "label": "Project Inactive Days", "fieldtype": "Int", "default": "7", "reqd": 1},
    {"fieldname": "high_risk_score", "label": "High Risk Score", "fieldtype": "Int", "default": "70", "reqd": 1},
    {"fieldname": "ai_enabled", "label": "AI Enabled", "fieldtype": "Check", "default": "0"},
    {"fieldname": "ai_provider", "label": "AI Provider", "fieldtype": "Select", "options": "Disabled\nOpenAI Compatible", "default": "Disabled"},
    {"fieldname": "ai_base_url", "label": "AI Base URL", "fieldtype": "Data"},
    {"fieldname": "ai_model", "label": "AI Model", "fieldtype": "Data"},
    {"fieldname": "ai_api_key", "label": "AI API Key", "fieldtype": "Password"}
  ],
  "permissions": [
    {"role": "AutoFlow Administrator", "read": 1, "write": 1},
    {"role": "System Manager", "read": 1, "write": 1}
  ]
}
```

控制器校验所有天数大于零、风险分数在 1 到 100 之间、启用 AI 时模型名称非空。

- [x] **Step 5: 迁移并运行安装测试**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --doctype "AutoFlow Settings"
```

Expected: 测试通过；重复执行 `migrate` 不新增重复角色或字段。

- [x] **Step 6: 提交系统基础数据**

```powershell
git add autoflow_360/setup autoflow_360/autoflow_360/doctype/autoflow_settings autoflow_360/hooks.py
git commit -m "feat: add AutoFlow roles settings and ERP links"
```

---

### Task 5: 实现客户项目主对象和状态机

**Files:**

- Create: `autoflow_360/autoflow_360/doctype/project_member/project_member.json`
- Create: `autoflow_360/autoflow_360/doctype/project_milestone/project_milestone.json`
- Create: `autoflow_360/autoflow_360/doctype/customer_project/customer_project.json`
- Create: `autoflow_360/autoflow_360/doctype/customer_project/customer_project.py`
- Create: `autoflow_360/autoflow_360/doctype/customer_project/customer_project.js`
- Create: `autoflow_360/autoflow_360/doctype/customer_project/test_customer_project.py`
- Create: `autoflow_360/tests/factories.py`
- Create: `autoflow_360/services/project_status.py`

**Interfaces:**

- Consumes: `Customer`、`CRM Deal`、`Company`、`User`。
- Produces: `Customer Project`、`set_project_stage(project_name, target_stage, reason=None)`、`derive_project_stage(project_name)`。

- [x] **Step 1: 写状态和日期校验失败测试**

```python
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, nowdate

from autoflow_360.tests.factories import make_customer_project


class TestCustomerProject(FrappeTestCase):
	def test_target_award_date_cannot_follow_customer_delivery(self):
		project = frappe.get_doc(
			{
				"doctype": "Customer Project",
				"project_name": "Invalid date project",
				"company": "_Test Company",
				"customer": "_Test Customer",
				"project_manager": "Administrator",
				"target_award_date": getdate(nowdate()) + timedelta(days=20),
				"customer_delivery_date": getdate(nowdate()) + timedelta(days=10),
			}
		)
		self.assertRaises(frappe.ValidationError, project.insert)

	def test_stage_cannot_skip_from_potential_to_awarded(self):
		project = make_customer_project("Stage guard project")
		project.stage = "已定点"
		self.assertRaises(frappe.ValidationError, project.save)

	def test_project_requires_at_least_one_member(self):
		project = make_customer_project("Member guard project", insert=False)
		project.set("project_members", [])
		self.assertRaises(frappe.ValidationError, project.insert)
```

测试辅助函数 `make_customer_project()` 固定创建合成客户、公司和负责人，不读取真实数据。

- [x] **Step 2: 运行测试并确认 DocType 尚不存在**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --doctype "Customer Project"
```

Expected: `Customer Project` 不存在。

- [x] **Step 3: 创建子表和客户项目字段**

`Customer Project` 必须具有以下稳定字段名：

```text
project_name Data required
company Link Company required
customer Link Customer required
crm_deal Link CRM Deal unique
product_family Data required
currency Link Currency required
expected_amount Currency currency
probability Percent
project_manager Link User required
project_members Table Project Member required
milestones Table Project Milestone
target_award_date Date required
customer_delivery_date Date required
last_meaningful_activity Datetime read-only
stage Select 潜在项目/样品阶段/报价阶段/已定点/订单履约/已交付/待回款/已结项/暂停/失败/取消
overall_risk_level Select 低/中/高 read-only
next_action Data
next_action_owner Link User
next_action_due_date Date
pause_reason Small Text
resume_date Date
failure_reason Small Text
cancellation_reason Small Text
closure_summary Long Text
is_demo Check read-only
demo_key Data unique read-only
data_classification Data read-only
```

命名规则使用 `AF-.YYYY.-.#####`，开启 `track_changes`，列表展示项目名称、客户、阶段、负责人、客户交期和风险等级。

- [x] **Step 4: 实现状态机和控制器校验**

```python
# autoflow_360/services/project_status.py
import frappe
from frappe import _

MAIN_TRANSITIONS = {
	"潜在项目": {"样品阶段"},
	"样品阶段": {"报价阶段"},
	"报价阶段": {"已定点"},
	"已定点": {"订单履约"},
	"订单履约": {"已交付"},
	"已交付": {"待回款"},
	"待回款": {"已结项"},
}
SIDE_STAGES = {"暂停", "失败", "取消"}


def validate_stage_transition(previous: str | None, current: str) -> None:
	if not previous or previous == current:
		return
	if current in SIDE_STAGES:
		return
	if current not in MAIN_TRANSITIONS.get(previous, set()):
		frappe.throw(_("Project stage cannot move from {0} to {1}.").format(previous, current))


def set_project_stage(project_name: str, target_stage: str, reason: str | None = None) -> str:
	project = frappe.get_doc("Customer Project", project_name)
	project.check_permission("write")
	if target_stage == "暂停":
		project.pause_reason = reason
	elif target_stage == "失败":
		project.failure_reason = reason
	elif target_stage == "取消":
		project.cancellation_reason = reason
	project.stage = target_stage
	project.save()
	return project.name


def derive_project_stage(project_name: str) -> str:
	project = frappe.get_doc("Customer Project", project_name)
	if project.stage in SIDE_STAGES or project.stage == "已结项":
		return project.stage
	if frappe.db.exists(
		"Sales Invoice",
		{
			"custom_customer_project": project.name,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
		},
	):
		return "待回款"
	if frappe.db.exists(
		"Delivery Note",
		{"custom_customer_project": project.name, "docstatus": 1},
	):
		return "已交付"
	if frappe.db.exists(
		"Sales Order",
		{"custom_customer_project": project.name, "docstatus": 1},
	):
		return "订单履约"
	if frappe.db.exists(
		"Quotation",
		{
			"custom_customer_project": project.name,
			"docstatus": 1,
			"custom_customer_confirmed": 1,
		},
	):
		return "已定点"
	if frappe.db.exists(
		"Quotation",
		{"custom_customer_project": project.name, "docstatus": 1},
	):
		return "报价阶段"
	if frappe.db.exists(
		"Sample Request",
		{
			"customer_project": project.name,
			"status": ["not in", ["客户认可", "拒绝"]],
		},
	):
		return "样品阶段"
	return "潜在项目"


def refresh_project_stage_from_document(doc, method: str | None = None) -> None:
	project_name = getattr(doc, "custom_customer_project", None)
	if not project_name:
		return
	project = frappe.get_doc("Customer Project", project_name)
	derived = derive_project_stage(project.name)
	if derived != project.stage:
		project.stage = derived
		project.save(ignore_permissions=True)
```

```python
# customer_project.py
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from autoflow_360.services.project_status import validate_stage_transition


class CustomerProject(Document):
	def validate(self) -> None:
		if getdate(self.target_award_date) > getdate(self.customer_delivery_date):
			frappe.throw(_("Target award date cannot be after customer delivery date."))
		if not self.project_members:
			frappe.throw(_("At least one project member is required."))
		previous = self.get_doc_before_save()
		validate_stage_transition(previous.stage if previous else None, self.stage)
		self._validate_side_stage_reason()

	def _validate_side_stage_reason(self) -> None:
		required = {
			"暂停": self.pause_reason,
			"失败": self.failure_reason,
			"取消": self.cancellation_reason,
		}
		if self.stage in required and not required[self.stage]:
			frappe.throw(_("A reason is required for stage {0}.").format(self.stage))
```

- [x] **Step 5: 迁移并运行状态测试**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --doctype "Customer Project"
```

Expected: 日期、成员和跳级测试通过。

- [x] **Step 6: 提交客户项目核心**

```powershell
git add autoflow_360/autoflow_360/doctype/project_member autoflow_360/autoflow_360/doctype/project_milestone autoflow_360/autoflow_360/doctype/customer_project autoflow_360/services/project_status.py autoflow_360/tests/factories.py
git commit -m "feat: add customer project lifecycle"
```

---

### Task 6: 实现 CRM 商机到客户项目的幂等转换

**Files:**

- Create: `autoflow_360/services/idempotency.py`
- Create: `autoflow_360/services/deal_conversion.py`
- Create: `autoflow_360/api/project.py`
- Create: `autoflow_360/public/js/crm_deal.js`
- Create: `autoflow_360/autoflow_360/doctype/customer_project/test_deal_conversion.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: `CRM Deal` 的 `organization`、`deal_owner`、`probability`、`expected_deal_value`、`expected_closure_date`。
- Produces: `create_project_from_deal(deal_name, company, customer, product_family, delivery_date) -> str`，重复请求返回同一项目名。

- [x] **Step 1: 写重复转换和权限失败测试**

```python
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, nowdate

from autoflow_360.services.deal_conversion import create_project_from_deal
from autoflow_360.tests.factories import make_crm_deal


class TestDealConversion(FrappeTestCase):
	def test_repeated_conversion_returns_same_project(self):
		deal = make_crm_deal("Synthetic Automotive Deal")
		arguments = {
			"deal_name": deal.name,
			"company": "_Test Company",
			"customer": "_Test Customer",
			"product_family": "Interior Material",
			"delivery_date": getdate(nowdate()) + timedelta(days=60),
		}
		first = create_project_from_deal(**arguments)
		second = create_project_from_deal(**arguments)
		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count("Customer Project", {"crm_deal": deal.name}),
			1,
		)

	def test_missing_deal_permission_is_rejected(self):
		deal = make_crm_deal("Protected Deal")
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, create_project_from_deal, deal.name, "_Test Company", "_Test Customer", "Material", nowdate())
```

- [x] **Step 2: 运行测试并确认服务缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.autoflow_360.doctype.customer_project.test_deal_conversion
```

Expected: `autoflow_360.services.deal_conversion` 无法导入。

- [x] **Step 3: 实现幂等键和转换事务**

```python
# autoflow_360/services/idempotency.py
import hashlib


def make_idempotency_key(operation: str, *parts: str) -> str:
	normalized = "|".join([operation, *(str(part).strip() for part in parts)])
	return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

```python
# autoflow_360/services/deal_conversion.py
import frappe
from frappe import _
from frappe.utils import getdate


def create_project_from_deal(
	deal_name: str,
	company: str,
	customer: str,
	product_family: str,
	delivery_date: str,
) -> str:
	if not frappe.has_permission("CRM Deal", "read", deal_name):
		raise frappe.PermissionError
	deal = frappe.get_doc("CRM Deal", deal_name)
	existing = frappe.db.get_value("Customer Project", {"crm_deal": deal.name}, "name")
	if existing:
		return existing
	if not all((company, customer, product_family, delivery_date)):
		frappe.throw(_("Company, customer, product family and delivery date are required."))

	project = frappe.get_doc(
		{
			"doctype": "Customer Project",
			"project_name": deal.organization_name or deal.organization or deal.name,
			"company": company,
			"customer": customer,
			"crm_deal": deal.name,
			"product_family": product_family,
			"currency": deal.currency or frappe.get_cached_value("Company", company, "default_currency"),
			"expected_amount": deal.expected_deal_value or deal.deal_value or 0,
			"probability": deal.probability or 0,
			"project_manager": deal.deal_owner or frappe.session.user,
			"target_award_date": deal.expected_closure_date or getdate(),
			"customer_delivery_date": getdate(delivery_date),
			"stage": "潜在项目",
			"project_members": [
				{
					"user": deal.deal_owner or frappe.session.user,
					"responsibility": "客户项目负责人",
				}
			],
		}
	)
	project.insert()
	return project.name
```

- [x] **Step 4: 暴露受权限保护的接口和 CRM 按钮**

```python
# autoflow_360/api/project.py
import frappe

from autoflow_360.services.deal_conversion import create_project_from_deal


@frappe.whitelist(methods=["POST"])
def convert_deal(
	deal_name: str,
	company: str,
	customer: str,
	product_family: str,
	delivery_date: str,
) -> str:
	return create_project_from_deal(deal_name, company, customer, product_family, delivery_date)
```

`hooks.py` 增加：

```python
doctype_js = {
	"CRM Deal": "public/js/crm_deal.js",
}
```

按钮只负责收集四个必填参数并调用接口；所有重复和权限判断保留在服务端。

- [x] **Step 5: 运行转换和静态测试**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.autoflow_360.doctype.customer_project.test_deal_conversion
python -m unittest discover -s tests/static -v
```

Expected: 重复调用仅存在一个项目；Guest 被拒绝。

- [x] **Step 6: 提交 CRM 转换**

```powershell
git add autoflow_360/services/idempotency.py autoflow_360/services/deal_conversion.py autoflow_360/api/project.py autoflow_360/public/js/crm_deal.js autoflow_360/autoflow_360/doctype/customer_project/test_deal_conversion.py autoflow_360/tests/factories.py autoflow_360/hooks.py
git commit -m "feat: convert CRM deals into customer projects"
```

---

### Task 7: 实现样品申请、检验、客户反馈和重新打样

**Files:**

- Create: `autoflow_360/autoflow_360/doctype/sample_item/sample_item.json`
- Create: `autoflow_360/autoflow_360/doctype/sample_request/sample_request.json`
- Create: `autoflow_360/autoflow_360/doctype/sample_request/sample_request.py`
- Create: `autoflow_360/autoflow_360/doctype/customer_feedback/customer_feedback.json`
- Create: `autoflow_360/autoflow_360/doctype/customer_feedback/customer_feedback.py`
- Create: `autoflow_360/services/sample_workflow.py`
- Create: `autoflow_360/api/portal.py`
- Create: `autoflow_360/www/customer-samples.html`
- Create: `autoflow_360/www/customer-samples.py`
- Create: `autoflow_360/templates/pages/customer_samples.html`
- Create: `autoflow_360/autoflow_360/doctype/sample_request/test_sample_request.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: `Customer Project`、`Item`、`Contact`、当前门户用户。
- Produces: `dispatch_sample(sample_name, carrier, tracking_number)`、`record_customer_feedback(sample_name, decision, comments, attachment=None)`、`create_resample(sample_name) -> str`。

- [x] **Step 1: 写检验门槛、反馈不可覆盖和重新打样测试**

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.services.sample_workflow import (
	create_resample,
	dispatch_sample,
	record_customer_feedback,
)
from autoflow_360.tests.factories import make_dispatched_sample, make_sample_request


class TestSampleRequest(FrappeTestCase):
	def test_uninspected_sample_cannot_be_dispatched(self):
		sample = make_sample_request(inspection_status="待检验")
		self.assertRaises(
			frappe.ValidationError,
			dispatch_sample,
			sample.name,
			"SF Express",
			"SF-SYNTHETIC-001",
		)

	def test_feedback_is_append_only(self):
		sample = make_dispatched_sample()
		first = record_customer_feedback(sample.name, "重新打样", "颜色不匹配")
		self.assertRaises(
			frappe.ValidationError,
			record_customer_feedback,
			sample.name,
			"客户认可",
			"覆盖旧结论",
		)
		self.assertTrue(frappe.db.exists("Customer Feedback", first))

	def test_resample_links_previous_round(self):
		sample = make_dispatched_sample()
		record_customer_feedback(sample.name, "重新打样", "调整厚度")
		resample_name = create_resample(sample.name)
		resample = frappe.get_doc("Sample Request", resample_name)
		self.assertEqual(resample.previous_sample_request, sample.name)
		self.assertEqual(resample.round_number, sample.round_number + 1)
		self.assertEqual(resample.status, "草稿")
```

- [x] **Step 2: 运行测试并确认样品对象缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --doctype "Sample Request"
```

Expected: `Sample Request` 不存在。

- [x] **Step 3: 创建样品和反馈模型**

`Sample Request` 稳定字段：

```text
customer_project Link Customer Project required
round_number Int required read-only
previous_sample_request Link Sample Request
purpose Data required
required_date Date required
customer_contact Link Contact required
status Select 草稿/待审批/制作中/检验中/已发出/等待反馈/客户认可/重新打样/拒绝
inspection_status Select 待检验/通过/不通过
items Table Sample Item required
carrier Data
tracking_number Data
dispatch_time Datetime read-only
feedback Link Customer Feedback read-only
```

`Sample Item` 稳定字段：

```text
item_code Link Item required
quantity Float required
uom Link UOM required
specification Small Text required
batch_no Data
inspection_result Select 待检验/通过/不通过
inspection_notes Small Text
```

`Customer Feedback` 稳定字段：

```text
sample_request Link Sample Request required unique
customer Link Customer required
contact Link Contact required
decision Select 客户认可/重新打样/拒绝 required
comments Small Text required
attachment Attach
submitted_by Link User read-only
submitted_at Datetime read-only
```

- [x] **Step 4: 实现服务端状态与门户权限**

```python
# autoflow_360/services/sample_workflow.py
import frappe
from frappe import _
from frappe.utils import now_datetime


def dispatch_sample(sample_name: str, carrier: str, tracking_number: str) -> str:
	sample = frappe.get_doc("Sample Request", sample_name)
	sample.check_permission("write")
	if sample.inspection_status != "通过":
		frappe.throw(_("Sample must pass inspection before dispatch."))
	if not carrier or not tracking_number:
		frappe.throw(_("Carrier and tracking number are required."))
	sample.status = "已发出"
	sample.carrier = carrier
	sample.tracking_number = tracking_number
	sample.dispatch_time = now_datetime()
	sample.save()
	return sample.name


def record_customer_feedback(
	sample_name: str,
	decision: str,
	comments: str,
	attachment: str | None = None,
) -> str:
	if decision not in {"客户认可", "重新打样", "拒绝"}:
		frappe.throw(_("Invalid feedback decision."))
	if frappe.db.exists("Customer Feedback", {"sample_request": sample_name}):
		frappe.throw(_("Customer feedback already exists and cannot be overwritten."))
	sample = frappe.get_doc("Sample Request", sample_name)
	if sample.status not in {"已发出", "等待反馈"}:
		frappe.throw(_("Only dispatched samples can receive feedback."))
	feedback = frappe.get_doc(
		{
			"doctype": "Customer Feedback",
			"sample_request": sample.name,
			"customer": frappe.db.get_value("Customer Project", sample.customer_project, "customer"),
			"contact": sample.customer_contact,
			"decision": decision,
			"comments": comments,
			"attachment": attachment,
			"submitted_by": frappe.session.user,
			"submitted_at": now_datetime(),
		}
	)
	feedback.insert()
	sample.db_set({"feedback": feedback.name, "status": decision})
	return feedback.name


def create_resample(sample_name: str) -> str:
	previous = frappe.get_doc("Sample Request", sample_name)
	if previous.status != "重新打样":
		frappe.throw(_("Resample is only allowed after a resample decision."))
	new_sample = frappe.copy_doc(previous)
	new_sample.name = None
	new_sample.round_number = previous.round_number + 1
	new_sample.previous_sample_request = previous.name
	new_sample.status = "草稿"
	new_sample.inspection_status = "待检验"
	new_sample.carrier = None
	new_sample.tracking_number = None
	new_sample.dispatch_time = None
	new_sample.feedback = None
	for item in new_sample.items:
		item.batch_no = None
		item.inspection_result = "待检验"
		item.inspection_notes = None
	new_sample.insert()
	return new_sample.name
```

门户接口先通过 `autoflow_360.permissions.portal.can_access_customer_project()` 校验用户所属客户，再调用 `record_customer_feedback()`。

- [x] **Step 5: 配置门户入口并运行测试**

`hooks.py` 增加：

```python
portal_menu_items = [
	{"title": "我的样品", "route": "/customer-samples", "role": "AutoFlow Customer Portal"},
]
```

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --doctype "Sample Request"
```

Expected: 未检验样品被阻止；反馈不能覆盖；重新打样轮次正确。

- [x] **Step 6: 提交样品闭环**

```powershell
git add autoflow_360/autoflow_360/doctype/sample_item autoflow_360/autoflow_360/doctype/sample_request autoflow_360/autoflow_360/doctype/customer_feedback autoflow_360/services/sample_workflow.py autoflow_360/api/portal.py autoflow_360/www autoflow_360/templates/pages/customer_samples.html autoflow_360/tests/factories.py autoflow_360/hooks.py
git commit -m "feat: add sample approval and customer feedback loop"
```

---

### Task 8: 实现报价门槛、价格权限和销售订单转换

**Files:**

- Create: `autoflow_360/services/sales_conversion.py`
- Create: `autoflow_360/autoflow_360/doctype/autoflow_approval_rule/autoflow_approval_rule.json`
- Create: `autoflow_360/autoflow_360/doctype/autoflow_approval_rule/autoflow_approval_rule.py`
- Create: `autoflow_360/autoflow_360/doctype/autoflow_approval_request/autoflow_approval_request.json`
- Create: `autoflow_360/autoflow_360/doctype/autoflow_approval_request/autoflow_approval_request.py`
- Create: `autoflow_360/autoflow_360/doctype/autoflow_approval_request/test_autoflow_approval_request.py`
- Create: `autoflow_360/setup/workflows.py`
- Create: `autoflow_360/public/js/quotation.js`
- Create: `autoflow_360/public/js/sales_order.js`
- Create: `autoflow_360/tests/test_sales_conversion.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/install.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: 已认可 `Sample Request`、ERPNext `Quotation`、当前用户审批额度。
- Produces: `validate_quotation_submission(doc)`、`create_sales_order_from_quotation(quotation_name) -> str`、可追溯审批请求。

- [ ] **Step 1: 写样品、有效期、审批和重复转换失败测试**

```python
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, nowdate

from autoflow_360.services.sales_conversion import create_sales_order_from_quotation
from autoflow_360.tests.factories import (
	make_approval_request,
	make_project_quotation,
	make_submitted_project_quotation,
)


class TestSalesConversion(FrappeTestCase):
	def test_unapproved_sample_blocks_quotation_submission(self):
		quotation = make_project_quotation(sample_decision="等待反馈")
		self.assertRaises(frappe.ValidationError, quotation.submit)

	def test_expired_quotation_cannot_convert(self):
		quotation = make_project_quotation(sample_decision="客户认可")
		quotation.valid_till = getdate(nowdate()) - timedelta(days=1)
		quotation.save()
		quotation.submit()
		self.assertRaises(frappe.ValidationError, create_sales_order_from_quotation, quotation.name)

	def test_repeated_conversion_returns_same_sales_order(self):
		quotation = make_submitted_project_quotation()
		first = create_sales_order_from_quotation(quotation.name)
		second = create_sales_order_from_quotation(quotation.name)
		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count("Sales Order", {"custom_source_quotation": quotation.name}),
			1,
		)

	def test_requester_cannot_approve_own_over_limit_request(self):
		request = make_approval_request(requested_by=frappe.session.user)
		self.assertRaises(frappe.PermissionError, request.approve, frappe.session.user)
```

- [ ] **Step 2: 运行测试并确认服务和审批对象缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_sales_conversion
```

Expected: 转换服务或审批 DocType 不存在。

- [ ] **Step 3: 创建审批规则和审批请求**

`AutoFlow Approval Rule` 字段：

```text
company Link Company required
document_type Select Sample Request/Quotation/Purchase Order/Delivery Date Change/Business Exception/Customer Project/Payment Entry
role Link Role required
amount_limit Currency
discount_limit Percent
risk_level Select 低/中/高
active Check default 1
```

`AutoFlow Approval Request` 字段：

```text
reference_doctype Link DocType required
reference_name Dynamic Link reference_doctype required
company Link Company required
approval_type Data required
requested_by Link User read-only
requested_at Datetime read-only
status Select 待审批/已通过/已退回/已拒绝
approver Link User
decision_at Datetime
decision_reason Small Text
request_snapshot JSON read-only
```

该 DocType 设置 `is_submittable: 1`。控制器方法 `approve(user)` 检查审批角色、公司、额度，且 `user != requested_by`：

```python
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class AutoFlowApprovalRequest(Document):
	def before_insert(self) -> None:
		self.requested_by = frappe.session.user
		self.requested_at = now_datetime()
		if not self.request_snapshot:
			source = frappe.get_doc(self.reference_doctype, self.reference_name)
			self.request_snapshot = json.dumps(
				source.as_dict(no_nulls=True),
				ensure_ascii=False,
				sort_keys=True,
				default=str,
			)

	@frappe.whitelist()
	def approve(self, user: str | None = None) -> str:
		user = user or frappe.session.user
		if user == self.requested_by:
			raise frappe.PermissionError
		roles = frappe.get_roles(user)
		allowed = frappe.db.exists(
			"AutoFlow Approval Rule",
			{
				"company": self.company,
				"document_type": self.reference_doctype,
				"role": ["in", roles],
				"active": 1,
			},
		)
		if not allowed:
			raise frappe.PermissionError
		if self.status != "待审批" or self.docstatus != 0:
			frappe.throw(_("Only pending requests can be approved."))
		self.status = "已通过"
		self.approver = user
		self.decision_at = now_datetime()
		self.save()
		self.submit()
		return self.name
```

`setup/workflows.py` 幂等创建样品和通用审批流程：

```python
import frappe


def ensure_workflows() -> None:
	for action_name in ("提交审批", "通过", "退回", "拒绝"):
		if not frappe.db.exists("Workflow Action Master", action_name):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": action_name}
			).insert(ignore_permissions=True)
	if frappe.db.exists("DocType", "Sample Request"):
		ensure_sample_workflow()
	if frappe.db.exists("DocType", "AutoFlow Approval Request"):
		ensure_approval_workflow()


def ensure_sample_workflow() -> None:
	if frappe.db.exists("Workflow", "AutoFlow Sample Approval"):
		return
	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": "AutoFlow Sample Approval",
			"document_type": "Sample Request",
			"is_active": 1,
			"workflow_state_field": "status",
			"states": [
				{"state": "草稿", "doc_status": "0", "allow_edit": "AutoFlow Project Manager"},
				{"state": "待审批", "doc_status": "0", "allow_edit": "AutoFlow Project Manager"},
				{"state": "制作中", "doc_status": "0", "allow_edit": "AutoFlow Project Manager"},
			],
			"transitions": [
				{"state": "草稿", "action": "提交审批", "next_state": "待审批", "allowed": "AutoFlow Project Manager"},
				{"state": "待审批", "action": "通过", "next_state": "制作中", "allowed": "AutoFlow Sales Operations"},
				{"state": "待审批", "action": "退回", "next_state": "草稿", "allowed": "AutoFlow Sales Operations"},
			],
		}
	).insert(ignore_permissions=True)


def ensure_approval_workflow() -> None:
	if frappe.db.exists("Workflow", "AutoFlow Business Approval"):
		return
	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": "AutoFlow Business Approval",
			"document_type": "AutoFlow Approval Request",
			"is_active": 1,
			"workflow_state_field": "status",
			"states": [
				{"state": "待审批", "doc_status": "0", "allow_edit": "All"},
				{"state": "已通过", "doc_status": "1", "allow_edit": "AutoFlow Administrator"},
				{"state": "已退回", "doc_status": "0", "allow_edit": "All"},
				{"state": "已拒绝", "doc_status": "2", "allow_edit": "AutoFlow Administrator"},
			],
			"transitions": [
				{"state": "待审批", "action": "通过", "next_state": "已通过", "allowed": "AutoFlow Executive"},
				{"state": "待审批", "action": "退回", "next_state": "已退回", "allowed": "AutoFlow Executive"},
				{"state": "待审批", "action": "拒绝", "next_state": "已拒绝", "allowed": "AutoFlow Executive"},
			],
		}
	).insert(ignore_permissions=True)
```

`install.py` 的 `after_install()` 在角色、字段完成后调用 `ensure_workflows()`；函数会先检查 DocType 是否存在，因此全新安装和后续迁移都可重复执行。

Task 8 完成后的 `install.py` 为：

```python
def after_install() -> None:
	from autoflow_360.setup.custom_fields import ensure_custom_fields
	from autoflow_360.setup.roles import ensure_roles
	from autoflow_360.setup.workflows import ensure_workflows

	ensure_roles()
	ensure_custom_fields()
	ensure_workflows()


def after_migrate() -> None:
	after_install()
```

- [ ] **Step 4: 实现报价校验和幂等转换**

```python
# autoflow_360/services/sales_conversion.py
import frappe
from frappe import _
from frappe.utils import getdate, nowdate


def _current_price_authority(company: str) -> tuple[float, float]:
	roles = frappe.get_roles(frappe.session.user)
	rules = frappe.get_all(
		"AutoFlow Approval Rule",
		filters={
			"company": company,
			"document_type": "Quotation",
			"role": ["in", roles],
			"active": 1,
		},
		fields=["amount_limit", "discount_limit"],
	)
	if not rules:
		return 0.0, 0.0
	return (
		max(float(rule.amount_limit or 0) for rule in rules),
		max(float(rule.discount_limit or 0) for rule in rules),
	)


def requires_price_approval(doc) -> bool:
	amount_limit, discount_limit = _current_price_authority(doc.company)
	if float(doc.grand_total or 0) > amount_limit:
		return True
	return any(
		float(item.discount_percentage or 0) > discount_limit
		or (
			float(getattr(item, "custom_floor_rate", 0) or 0) > 0
			and float(item.rate or 0) < float(item.custom_floor_rate)
		)
		for item in doc.items
	)


def has_approved_request(reference_doctype: str, reference_name: str) -> bool:
	return bool(
		frappe.db.exists(
			"AutoFlow Approval Request",
			{
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"status": "已通过",
				"docstatus": 1,
			},
		)
	)


def validate_quotation_submission(doc, method: str | None = None) -> None:
	if not doc.custom_customer_project:
		return
	approved_sample = frappe.db.exists(
		"Sample Request",
		{
			"customer_project": doc.custom_customer_project,
			"status": "客户认可",
		},
	)
	if not approved_sample:
		frappe.throw(_("A customer-approved sample is required before quotation submission."))
	if doc.valid_till and getdate(doc.valid_till) < getdate(nowdate()):
		frappe.throw(_("Expired quotation cannot be submitted."))
	if requires_price_approval(doc) and not has_approved_request("Quotation", doc.name):
		frappe.throw(_("Quotation exceeds the current user's price authority."))


def create_sales_order_from_quotation(quotation_name: str) -> str:
	quotation = frappe.get_doc("Quotation", quotation_name)
	quotation.check_permission("read")
	if quotation.docstatus != 1:
		frappe.throw(_("Quotation must be submitted before conversion."))
	if quotation.valid_till and getdate(quotation.valid_till) < getdate(nowdate()):
		frappe.throw(_("Expired quotation cannot be converted."))
	if not quotation.custom_customer_confirmed:
		frappe.throw(_("Customer has not confirmed this quotation."))
	existing = frappe.db.get_value(
		"Sales Order",
		{"custom_source_quotation": quotation.name, "docstatus": ["<", 2]},
		"name",
	)
	if existing:
		return existing
	from erpnext.selling.doctype.quotation.quotation import make_sales_order

	order = make_sales_order(quotation.name)
	order.custom_customer_project = quotation.custom_customer_project
	order.custom_source_quotation = quotation.name
	order.insert()
	return order.name
```

`setup/custom_fields.py` 为 `Sales Order` 增加只读字段 `custom_source_quotation`，为 `Quotation Item` 增加 `custom_floor_rate`，并确保金额和折扣不为负。

同时为 `Quotation` 增加 `custom_customer_confirmed` 勾选字段。`create_sales_order_from_quotation()` 必须校验该字段为真，否则返回“客户尚未确认报价”并停止转换。

- [ ] **Step 5: 注册标准单据钩子并运行测试**

`hooks.py` 合并为：

```python
doctype_js = {
	"CRM Deal": "public/js/crm_deal.js",
	"Quotation": "public/js/quotation.js",
	"Sales Order": "public/js/sales_order.js",
}

doc_events = {
	"Quotation": {
		"before_submit": "autoflow_360.services.sales_conversion.validate_quotation_submission",
	},
}
```

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_sales_conversion
```

Expected: 四项测试均通过。

- [ ] **Step 6: 提交报价和审批闭环**

```powershell
git add autoflow_360/services/sales_conversion.py autoflow_360/autoflow_360/doctype/autoflow_approval_rule autoflow_360/autoflow_360/doctype/autoflow_approval_request autoflow_360/public/js/quotation.js autoflow_360/public/js/sales_order.js autoflow_360/tests/test_sales_conversion.py autoflow_360/tests/factories.py autoflow_360/setup/custom_fields.py autoflow_360/setup/workflows.py autoflow_360/install.py autoflow_360/hooks.py
git commit -m "feat: enforce quotation approval and sales conversion"
```

---

### Task 9: 实现销售订单驱动的物料缺口和采购需求

**Files:**

- Create: `autoflow_360/services/material_planning.py`
- Create: `autoflow_360/autoflow_360/doctype/project_material_plan/project_material_plan.json`
- Create: `autoflow_360/autoflow_360/doctype/project_material_plan/project_material_plan.py`
- Create: `autoflow_360/autoflow_360/doctype/project_material_plan_item/project_material_plan_item.json`
- Create: `autoflow_360/tests/test_material_planning.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: 已提交 `Sales Order`、`Bin.actual_qty`、保留数量、在途采购和物料安全库存。
- Produces: `calculate_material_gap(sales_order_name) -> list[MaterialGap]`、`create_material_request(sales_order_name) -> str | None`。

- [ ] **Step 1: 写缺口计算和重复需求测试**

```python
from frappe.tests.utils import FrappeTestCase
import frappe

from autoflow_360.services.material_planning import (
	calculate_material_gap,
	create_material_request,
)
from autoflow_360.tests.factories import make_sales_order, set_warehouse_stock


class TestMaterialPlanning(FrappeTestCase):
	def test_available_stock_reduces_required_quantity(self):
		order = make_sales_order(item_code="_Test Item", quantity=10)
		set_warehouse_stock("_Test Item", "_Test Warehouse - _TC", 4)
		gaps = calculate_material_gap(order.name)
		self.assertEqual(len(gaps), 1)
		self.assertEqual(gaps[0].required_qty, 6)

	def test_no_request_is_created_without_gap(self):
		order = make_sales_order(item_code="_Test Item", quantity=5)
		set_warehouse_stock("_Test Item", "_Test Warehouse - _TC", 10)
		self.assertIsNone(create_material_request(order.name))

	def test_repeated_request_creation_is_idempotent(self):
		order = make_sales_order(item_code="_Test Item", quantity=10)
		set_warehouse_stock("_Test Item", "_Test Warehouse - _TC", 0)
		first = create_material_request(order.name)
		second = create_material_request(order.name)
		self.assertEqual(first, second)
```

- [ ] **Step 2: 运行测试并确认规划服务缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_material_planning
```

Expected: `material_planning` 无法导入。

- [ ] **Step 3: 定义可解释物料缺口类型**

```python
# autoflow_360/services/material_planning.py
from dataclasses import dataclass

import frappe
from frappe import _


@dataclass(frozen=True, slots=True)
class MaterialGap:
	item_code: str
	warehouse: str
	ordered_qty: float
	available_qty: float
	incoming_qty: float
	safety_stock: float
	required_qty: float


def calculate_material_gap(sales_order_name: str) -> list[MaterialGap]:
	order = frappe.get_doc("Sales Order", sales_order_name)
	order.check_permission("read")
	gaps: list[MaterialGap] = []
	for item in order.items:
		warehouse = item.warehouse or order.set_warehouse
		if not warehouse:
			frappe.throw(_("Warehouse is required for item {0}.").format(item.item_code))
		bin_values = frappe.db.get_value(
			"Bin",
			{"item_code": item.item_code, "warehouse": warehouse},
			["actual_qty", "reserved_qty", "ordered_qty"],
			as_dict=True,
		) or {}
		available = max(float(bin_values.get("actual_qty", 0)) - float(bin_values.get("reserved_qty", 0)), 0)
		incoming = max(float(bin_values.get("ordered_qty", 0)), 0)
		safety_stock = max(float(frappe.db.get_value("Item", item.item_code, "safety_stock") or 0), 0)
		required = max(float(item.stock_qty) + safety_stock - available - incoming, 0)
		if required > 0:
			gaps.append(
				MaterialGap(
					item_code=item.item_code,
					warehouse=warehouse,
					ordered_qty=float(item.stock_qty),
					available_qty=available,
					incoming_qty=incoming,
					safety_stock=safety_stock,
					required_qty=required,
				)
			)
	return gaps


def has_approved_closure_request(project_name: str) -> bool:
	return bool(
		frappe.db.exists(
			"AutoFlow Approval Request",
			{
				"reference_doctype": "Customer Project",
				"reference_name": project_name,
				"approval_type": "项目结项",
				"status": "已通过",
				"docstatus": 1,
			},
		)
	)
```

- [ ] **Step 4: 实现物料需求幂等创建**

```python
def create_material_request(sales_order_name: str) -> str | None:
	order = frappe.get_doc("Sales Order", sales_order_name)
	order.check_permission("read")
	if order.docstatus != 1:
		frappe.throw(_("Sales Order must be submitted."))
	existing = frappe.db.get_value(
		"Material Request",
		{"custom_source_sales_order": order.name, "docstatus": ["<", 2]},
		"name",
	)
	if existing:
		return existing
	gaps = calculate_material_gap(order.name)
	if not gaps:
		return None
	request = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": order.company,
			"schedule_date": order.delivery_date,
			"custom_customer_project": order.custom_customer_project,
			"custom_source_sales_order": order.name,
			"items": [
				{
					"item_code": gap.item_code,
					"qty": gap.required_qty,
					"warehouse": gap.warehouse,
					"schedule_date": order.delivery_date,
				}
				for gap in gaps
			],
		}
	)
	request.insert()
	return request.name
```

`setup/custom_fields.py` 为 `Material Request` 增加只读 `custom_source_sales_order`。

- [ ] **Step 5: 运行规划测试并验证负数边界**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_material_planning
```

Expected: 库存充足不建单；库存缺口正确；重复调用返回同一需求。

- [ ] **Step 6: 提交物料规划**

```powershell
git add autoflow_360/services/material_planning.py autoflow_360/autoflow_360/doctype/project_material_plan autoflow_360/autoflow_360/doctype/project_material_plan_item autoflow_360/tests/test_material_planning.py autoflow_360/tests/factories.py autoflow_360/setup/custom_fields.py autoflow_360/hooks.py
git commit -m "feat: plan material gaps from sales orders"
```

---

### Task 10: 实现询价、供应商报价、采购订单和供应商门户

**Files:**

- Create: `autoflow_360/services/procurement.py`
- Create: `autoflow_360/services/project_linking.py`
- Create: `autoflow_360/permissions/portal.py`
- Create: `autoflow_360/www/supplier-rfqs.html`
- Create: `autoflow_360/www/supplier-rfqs.py`
- Create: `autoflow_360/www/supplier-orders.html`
- Create: `autoflow_360/www/supplier-orders.py`
- Create: `autoflow_360/templates/pages/supplier_rfqs.html`
- Create: `autoflow_360/templates/pages/supplier_orders.html`
- Create: `autoflow_360/tests/test_procurement.py`
- Create: `autoflow_360/tests/test_supplier_portal.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/api/portal.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: `Material Request`、`Request for Quotation`、`Supplier Quotation`、`Purchase Order`、Portal User → Contact → Supplier。
- Produces: `make_project_rfq(material_request_name, suppliers) -> str`、`submit_supplier_quote(...) -> str`、`update_supplier_eta(purchase_order, eta) -> str`。

- [ ] **Step 1: 写供应商隔离、采购关联和交期测试**

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.services.procurement import make_project_rfq, update_supplier_eta
from autoflow_360.tests.factories import (
	make_payment_entry_for_invoice,
	make_project_material_request,
	make_purchase_invoice_from_order,
	make_purchase_order,
	make_purchase_receipt_from_order,
	make_submitted_project_purchase_order,
	make_supplier_quotation,
	make_two_suppliers_with_portal_users,
)


class TestProcurement(FrappeTestCase):
	def test_rfq_keeps_project_and_material_request_source(self):
		request = make_project_material_request()
		rfq_name = make_project_rfq(request.name, ["_Test Supplier"])
		rfq = frappe.get_doc("Request for Quotation", rfq_name)
		self.assertEqual(rfq.custom_customer_project, request.custom_customer_project)
		self.assertEqual(rfq.custom_source_material_request, request.name)

	def test_supplier_cannot_read_competitor_quote(self):
		first_supplier, second_supplier = make_two_suppliers_with_portal_users()
		quote = make_supplier_quotation(second_supplier)
		frappe.set_user(first_supplier.portal_user)
		self.assertFalse(frappe.has_permission("Supplier Quotation", "read", quote.name))

	def test_eta_change_keeps_history(self):
		order = make_purchase_order()
		update_supplier_eta(order.name, "2026-09-01", "供应商首次确认")
		update_supplier_eta(order.name, "2026-09-05", "供应商产能调整")
		self.assertEqual(
			frappe.db.count("Supplier ETA History", {"purchase_order": order.name}),
			2,
		)

	def test_purchase_receipt_invoice_and_payment_keep_project_link(self):
		order = make_submitted_project_purchase_order()
		receipt = make_purchase_receipt_from_order(order.name)
		receipt.insert()
		receipt.submit()
		invoice = make_purchase_invoice_from_order(order.name)
		invoice.insert()
		invoice.submit()
		payment = make_payment_entry_for_invoice(invoice.name)
		payment.insert()
		payment.submit()
		for doc in (receipt, invoice, payment):
			self.assertEqual(doc.custom_customer_project, order.custom_customer_project)
```

- [ ] **Step 2: 运行测试并确认采购扩展缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_procurement
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_supplier_portal
```

Expected: 采购服务或 `Supplier ETA History` 不存在。

- [ ] **Step 3: 创建采购来源与交期历史字段**

新增 `Supplier ETA History`：

```text
purchase_order Link Purchase Order required
previous_eta Date
new_eta Date required
changed_by Link User read-only
changed_at Datetime read-only
change_reason Small Text required
```

自定义字段：

```text
Request for Quotation.custom_source_material_request Link Material Request read-only
Supplier Quotation.custom_source_rfq Link Request for Quotation read-only
Purchase Order.custom_source_supplier_quotation Link Supplier Quotation read-only
Purchase Order.custom_supplier_eta Date
```

- [ ] **Step 4: 实现采购服务和门户服务端校验**

```python
# autoflow_360/permissions/portal.py
import frappe


def _party_for_user(party_doctype: str, user: str | None = None) -> str | None:
	user = user or frappe.session.user
	contact = frappe.db.get_value("Contact", {"user": user}, "name")
	if not contact:
		return None
	return frappe.db.get_value(
		"Dynamic Link",
		{"parent": contact, "parenttype": "Contact", "link_doctype": party_doctype},
		"link_name",
	)


def get_customer_for_user(user: str | None = None) -> str | None:
	return _party_for_user("Customer", user)


def get_supplier_for_user(user: str | None = None) -> str | None:
	return _party_for_user("Supplier", user)


def supplier_document_is_allowed(
	doc,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool | None:
	user = user or frappe.session.user
	if "AutoFlow Supplier Portal" not in frappe.get_roles(user):
		return None
	supplier = get_supplier_for_user(user)
	return bool(supplier and getattr(doc, "supplier", None) == supplier)
```

```python
# autoflow_360/services/procurement.py
import frappe
from frappe import _
from frappe.utils import getdate, now_datetime


def make_project_rfq(material_request_name: str, suppliers: list[str]) -> str:
	request = frappe.get_doc("Material Request", material_request_name)
	request.check_permission("read")
	if request.docstatus != 1:
		frappe.throw(_("Material Request must be submitted."))
	unique_suppliers = list(dict.fromkeys(item.strip() for item in suppliers if item.strip()))
	if not unique_suppliers:
		frappe.throw(_("At least one supplier is required."))
	existing = frappe.db.get_value(
		"Request for Quotation",
		{"custom_source_material_request": request.name, "docstatus": ["<", 2]},
		"name",
	)
	if existing:
		return existing
	rfq = frappe.get_doc(
		{
			"doctype": "Request for Quotation",
			"company": request.company,
			"transaction_date": getdate(),
			"schedule_date": max(getdate(item.schedule_date) for item in request.items),
			"custom_customer_project": request.custom_customer_project,
			"custom_source_material_request": request.name,
			"suppliers": [{"supplier": supplier} for supplier in unique_suppliers],
			"items": [
				{
					"item_code": item.item_code,
					"description": item.description,
					"qty": item.qty,
					"uom": item.uom,
					"warehouse": item.warehouse,
					"schedule_date": item.schedule_date,
					"material_request": request.name,
					"material_request_item": item.name,
				}
				for item in request.items
			],
		}
	)
	rfq.insert()
	return rfq.name


def submit_supplier_quote(
	rfq_name: str,
	items: list[dict],
	valid_till: str,
) -> str:
	from autoflow_360.permissions.portal import get_supplier_for_user

	supplier = get_supplier_for_user()
	if not supplier:
		raise frappe.PermissionError
	rfq = frappe.get_doc("Request for Quotation", rfq_name)
	if not any(row.supplier == supplier for row in rfq.suppliers):
		raise frappe.PermissionError
	if frappe.db.exists(
		"Supplier Quotation",
		{"custom_source_rfq": rfq.name, "supplier": supplier, "docstatus": ["<", 2]},
	):
		frappe.throw(_("A current quotation already exists for this RFQ."))
	allowed_items = {row.item_code: row for row in rfq.items}
	if not items:
		frappe.throw(_("At least one quotation item is required."))
	quote_items = []
	for item in items:
		item_code = item.get("item_code")
		if item_code not in allowed_items:
			frappe.throw(_("Item {0} is not part of this RFQ.").format(item_code))
		rate = float(item.get("rate") or 0)
		if rate < 0:
			frappe.throw(_("Quotation rate cannot be negative."))
		source = allowed_items[item_code]
		quote_items.append(
			{
				"item_code": item_code,
				"qty": source.qty,
				"uom": source.uom,
				"rate": rate,
				"schedule_date": item.get("schedule_date") or source.schedule_date,
				"request_for_quotation": rfq.name,
				"request_for_quotation_item": source.name,
			}
		)
	quote = frappe.get_doc(
		{
			"doctype": "Supplier Quotation",
			"supplier": supplier,
			"company": rfq.company,
			"transaction_date": getdate(),
			"valid_till": getdate(valid_till),
			"custom_customer_project": rfq.custom_customer_project,
			"custom_source_rfq": rfq.name,
			"items": quote_items,
		}
	)
	quote.insert(ignore_permissions=True)
	return quote.name


def update_supplier_eta(purchase_order: str, eta: str, reason: str) -> str:
	order = frappe.get_doc("Purchase Order", purchase_order)
	order.check_permission("write")
	new_eta = getdate(eta)
	if new_eta < getdate(order.transaction_date):
		frappe.throw(_("Supplier ETA cannot be before the purchase order date."))
	frappe.get_doc(
		{
			"doctype": "Supplier ETA History",
			"purchase_order": order.name,
			"previous_eta": order.custom_supplier_eta,
			"new_eta": new_eta,
			"changed_by": frappe.session.user,
			"changed_at": now_datetime(),
			"change_reason": reason,
		}
	).insert()
	order.db_set("custom_supplier_eta", new_eta)
	return order.name
```

```python
# autoflow_360/services/project_linking.py
import frappe
from frappe import _

ROW_SOURCE_FIELDS = {
	"Purchase Receipt": ("purchase_order", "Purchase Order"),
	"Purchase Invoice": ("purchase_order", "Purchase Order"),
	"Delivery Note": ("against_sales_order", "Sales Order"),
	"Sales Invoice": ("sales_order", "Sales Order"),
}


def propagate_project_link(doc, method: str | None = None) -> None:
	if getattr(doc, "custom_customer_project", None):
		return
	projects: set[str] = set()
	if doc.doctype in ROW_SOURCE_FIELDS:
		fieldname, source_doctype = ROW_SOURCE_FIELDS[doc.doctype]
		for row in doc.items:
			source_name = getattr(row, fieldname, None)
			if source_name:
				project = frappe.db.get_value(source_doctype, source_name, "custom_customer_project")
				if project:
					projects.add(project)
	elif doc.doctype == "Payment Entry":
		for row in doc.references:
			if row.reference_doctype not in {"Sales Invoice", "Purchase Invoice"}:
				continue
			project = frappe.db.get_value(
				row.reference_doctype,
				row.reference_name,
				"custom_customer_project",
			)
			if project:
				projects.add(project)
	if len(projects) > 1:
		frappe.throw(_("One document cannot combine multiple customer projects."))
	if projects:
		doc.custom_customer_project = projects.pop()
```

- [ ] **Step 5: 配置门户入口和权限钩子**

`hooks.py` 增加：

```python
portal_menu_items = [
	{"title": "我的样品", "route": "/customer-samples", "role": "AutoFlow Customer Portal"},
	{"title": "询价", "route": "/supplier-rfqs", "role": "AutoFlow Supplier Portal"},
	{"title": "采购订单", "route": "/supplier-orders", "role": "AutoFlow Supplier Portal"},
]

has_permission = {
	"Supplier Quotation": "autoflow_360.permissions.portal.supplier_document_is_allowed",
	"Purchase Order": "autoflow_360.permissions.portal.supplier_document_is_allowed",
}

doc_events.update(
	{
		"Purchase Receipt": {
			"before_insert": "autoflow_360.services.project_linking.propagate_project_link",
		},
		"Purchase Invoice": {
			"before_insert": "autoflow_360.services.project_linking.propagate_project_link",
		},
		"Payment Entry": {
			"before_insert": "autoflow_360.services.project_linking.propagate_project_link",
		},
	}
)
```

内部用户返回 `None`，继续使用 ERPNext 标准权限；门户用户返回严格布尔结果。

- [ ] **Step 6: 运行采购和门户测试**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_procurement
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_supplier_portal
```

Expected: 供应商不能查看竞争对手报价；来源关系和交期历史正确。

- [ ] **Step 7: 提交采购协同**

```powershell
git add autoflow_360/services/procurement.py autoflow_360/services/project_linking.py autoflow_360/permissions/portal.py autoflow_360/www/supplier-rfqs* autoflow_360/www/supplier-orders* autoflow_360/templates/pages/supplier_* autoflow_360/tests/test_procurement.py autoflow_360/tests/test_supplier_portal.py autoflow_360/tests/factories.py autoflow_360/api/portal.py autoflow_360/hooks.py autoflow_360/setup/custom_fields.py
git commit -m "feat: add procurement flow and supplier portal"
```

---

### Task 11: 实现采购收货、库存校验、客户交付与签收

**Files:**

- Create: `autoflow_360/services/delivery.py`
- Create: `autoflow_360/autoflow_360/doctype/customer_receipt/customer_receipt.json`
- Create: `autoflow_360/autoflow_360/doctype/customer_receipt/customer_receipt.py`
- Create: `autoflow_360/www/customer-deliveries.html`
- Create: `autoflow_360/www/customer-deliveries.py`
- Create: `autoflow_360/templates/pages/customer_deliveries.html`
- Create: `autoflow_360/tests/test_delivery.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/api/portal.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: `Purchase Receipt`、`Bin`、`Sales Order`、`Delivery Note`、客户门户身份。
- Produces: `validate_delivery_stock(doc)`、`confirm_customer_receipt(delivery_note, proof_file=None) -> str`。

- [ ] **Step 1: 写库存不足、超发和越权签收测试**

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.services.delivery import confirm_customer_receipt
from autoflow_360.tests.factories import (
	make_customer_portal_user,
	make_delivery_note,
	make_submitted_delivery_note,
)


class TestDelivery(FrappeTestCase):
	def test_insufficient_stock_blocks_delivery_submission(self):
		delivery = make_delivery_note(quantity=10, available_stock=4)
		self.assertRaises(frappe.ValidationError, delivery.submit)

	def test_customer_cannot_confirm_another_customer_delivery(self):
		delivery = make_submitted_delivery_note(customer="_Test Customer 2")
		frappe.set_user(make_customer_portal_user("_Test Customer"))
		self.assertRaises(
			frappe.PermissionError,
			confirm_customer_receipt,
			delivery.name,
			None,
		)

	def test_receipt_is_idempotent(self):
		delivery = make_submitted_delivery_note()
		first = confirm_customer_receipt(delivery.name)
		second = confirm_customer_receipt(delivery.name)
		self.assertEqual(first, second)
```

- [ ] **Step 2: 运行测试并确认交付服务缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_delivery
```

Expected: `delivery` 服务或 `Customer Receipt` 不存在。

- [ ] **Step 3: 创建签收模型和库存校验**

`Customer Receipt` 字段：

```text
delivery_note Link Delivery Note required unique
customer Link Customer required
customer_project Link Customer Project required
received_by Link Contact
received_at Datetime read-only
proof_file Attach
portal_user Link User read-only
```

```python
# autoflow_360/services/delivery.py
import frappe
from frappe import _
from frappe.utils import now_datetime


def customer_delivery_is_allowed(delivery, user: str) -> bool:
	from autoflow_360.permissions.portal import get_customer_for_user

	if "AutoFlow Customer Portal" not in frappe.get_roles(user):
		return delivery.has_permission("read")
	customer = get_customer_for_user(user)
	return bool(customer and delivery.customer == customer)


def validate_delivery_stock(doc, method: str | None = None) -> None:
	if not doc.custom_customer_project:
		return
	for item in doc.items:
		available = frappe.db.get_value(
			"Bin",
			{"item_code": item.item_code, "warehouse": item.warehouse},
			"actual_qty",
		) or 0
		if float(available) < float(item.stock_qty):
			frappe.throw(
				_("Insufficient stock for {0}: required {1}, available {2}.").format(
					item.item_code,
					item.stock_qty,
					available,
				)
			)


def confirm_customer_receipt(delivery_note: str, proof_file: str | None = None) -> str:
	delivery = frappe.get_doc("Delivery Note", delivery_note)
	if delivery.docstatus != 1:
		frappe.throw(_("Delivery Note must be submitted."))
	if not customer_delivery_is_allowed(delivery, frappe.session.user):
		raise frappe.PermissionError
	existing = frappe.db.get_value("Customer Receipt", {"delivery_note": delivery.name}, "name")
	if existing:
		return existing
	receipt = frappe.get_doc(
		{
			"doctype": "Customer Receipt",
			"delivery_note": delivery.name,
			"customer": delivery.customer,
			"customer_project": delivery.custom_customer_project,
			"received_at": now_datetime(),
			"proof_file": proof_file,
			"portal_user": frappe.session.user,
		}
	)
	receipt.insert(ignore_permissions=True)
	return receipt.name
```

- [ ] **Step 4: 注册交付钩子和客户门户**

`hooks.py` 增加：

```python
doc_events.update(
	{
		"Sales Order": {
			"on_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
		},
		"Delivery Note": {
			"before_insert": "autoflow_360.services.project_linking.propagate_project_link",
			"before_submit": "autoflow_360.services.delivery.validate_delivery_stock",
			"on_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
		},
		"Sales Invoice": {
			"before_insert": "autoflow_360.services.project_linking.propagate_project_link",
			"on_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
			"on_update_after_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
		},
		"Payment Entry": {
			"on_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
		},
	}
)
```

客户门户列表必须使用 `frappe.get_list()` 和客户过滤，不使用绕过权限的 `frappe.get_all()`。

- [ ] **Step 5: 运行交付测试**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_delivery
```

Expected: 库存不足被阻止；跨客户签收被拒绝；重复签收返回同一记录。

- [ ] **Step 6: 提交库存交付闭环**

```powershell
git add autoflow_360/services/delivery.py autoflow_360/autoflow_360/doctype/customer_receipt autoflow_360/www/customer-deliveries* autoflow_360/templates/pages/customer_deliveries.html autoflow_360/tests/test_delivery.py autoflow_360/tests/factories.py autoflow_360/api/portal.py autoflow_360/hooks.py
git commit -m "feat: enforce stock and customer delivery receipt"
```

---

### Task 12: 实现开票、回款与严格项目结项

**Files:**

- Create: `autoflow_360/services/project_closure.py`
- Create: `autoflow_360/tests/test_project_closure.py`
- Modify: `autoflow_360/tests/factories.py`
- Create: `autoflow_360/public/js/customer_project.js`
- Modify: `autoflow_360/api/project.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: 已提交销售订单、交货单、销售发票、付款记录和高风险异常。
- Produces: `get_closure_gaps(project_name) -> list[ClosureGap]`、`close_project(project_name, summary) -> str`。

- [ ] **Step 1: 写交付、发票、回款和异常门槛测试**

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.services.project_closure import close_project, get_closure_gaps
from autoflow_360.tests.factories import make_fulfilled_project


class TestProjectClosure(FrappeTestCase):
	def test_unpaid_invoice_blocks_closure(self):
		project = make_fulfilled_project(outstanding_amount=100)
		gaps = get_closure_gaps(project.name)
		self.assertIn("UNPAID_RECEIVABLE", {gap.code for gap in gaps})
		self.assertRaises(frappe.ValidationError, close_project, project.name, "复盘")

	def test_complete_evidence_allows_closure(self):
		project = make_fulfilled_project(outstanding_amount=0)
		result = close_project(project.name, "项目按计划完成，交付与回款证据齐全。")
		self.assertEqual(result, project.name)
		self.assertEqual(frappe.db.get_value("Customer Project", project.name, "stage"), "已结项")
```

- [ ] **Step 2: 运行测试并确认结项服务缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_project_closure
```

Expected: `project_closure` 无法导入。

- [ ] **Step 3: 实现逐项可解释的结项缺口**

```python
# autoflow_360/services/project_closure.py
from dataclasses import dataclass

import frappe
from frappe import _


@dataclass(frozen=True, slots=True)
class ClosureGap:
	code: str
	message: str
	reference_doctype: str | None = None
	reference_name: str | None = None


def get_closure_gaps(project_name: str) -> list[ClosureGap]:
	project = frappe.get_doc("Customer Project", project_name)
	project.check_permission("read")
	gaps: list[ClosureGap] = []
	orders = frappe.get_all(
		"Sales Order",
		filters={"custom_customer_project": project.name, "docstatus": 1},
		fields=["name", "status", "per_delivered", "per_billed"],
	)
	if not orders:
		gaps.append(ClosureGap("NO_SALES_ORDER", _("No submitted Sales Order exists.")))
	for order in orders:
		if float(order.per_delivered or 0) < 100:
			gaps.append(ClosureGap("DELIVERY_INCOMPLETE", _("Delivery is incomplete."), "Sales Order", order.name))
		if float(order.per_billed or 0) < 100:
			gaps.append(ClosureGap("BILLING_INCOMPLETE", _("Billing is incomplete."), "Sales Order", order.name))
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"custom_customer_project": project.name, "docstatus": 1},
		fields=["name", "outstanding_amount"],
	)
	for invoice in invoices:
		if float(invoice.outstanding_amount or 0) > 0:
			gaps.append(ClosureGap("UNPAID_RECEIVABLE", _("Receivable is unpaid."), "Sales Invoice", invoice.name))
	if frappe.db.exists("DocType", "Business Exception"):
		for exception in frappe.get_all(
			"Business Exception",
			filters={
				"customer_project": project.name,
				"risk_level": "高",
				"status": ["not in", ["已关闭", "已取消"]],
			},
			fields=["name"],
		):
			gaps.append(
				ClosureGap(
					"OPEN_HIGH_EXCEPTION",
					_("A high-risk exception is still open."),
					"Business Exception",
					exception.name,
				)
			)
	return gaps
```

- [ ] **Step 4: 实现结项接口和审批门槛**

```python
def close_project(project_name: str, summary: str) -> str:
	project = frappe.get_doc("Customer Project", project_name)
	project.check_permission("write")
	if not summary or len(summary.strip()) < 10:
		frappe.throw(_("Closure summary must contain at least 10 characters."))
	gaps = get_closure_gaps(project.name)
	if gaps:
		frappe.throw("<br>".join(gap.message for gap in gaps))
	if not has_approved_closure_request(project.name):
		frappe.throw(_("Approved project closure request is required."))
	project.closure_summary = summary.strip()
	project.stage = "已结项"
	project.save()
	return project.name
```

API 使用 `@frappe.whitelist(methods=["POST"])`，页面先显示 `get_closure_gaps()` 再允许发起审批或结项。

- [ ] **Step 5: 运行结项测试**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_project_closure
```

Expected: 缺口代码准确；证据齐全且审批通过后才可结项。

- [ ] **Step 6: 提交财务与结项闭环**

```powershell
git add autoflow_360/services/project_closure.py autoflow_360/tests/test_project_closure.py autoflow_360/tests/factories.py autoflow_360/public/js/customer_project.js autoflow_360/api/project.py autoflow_360/hooks.py
git commit -m "feat: close projects only after delivery billing and payment"
```

---

### Task 13: 实现可解释、去重的确定性风险引擎

**Files:**

- Create: `autoflow_360/autoflow_360/doctype/project_risk/project_risk.json`
- Create: `autoflow_360/autoflow_360/doctype/project_risk/project_risk.py`
- Create: `autoflow_360/risk_engine/types.py`
- Create: `autoflow_360/risk_engine/rules.py`
- Create: `autoflow_360/risk_engine/service.py`
- Create: `autoflow_360/risk_engine/scheduled.py`
- Create: `autoflow_360/tests/test_risk_engine.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: 项目、节点、样品、报价、库存、采购订单、异常、发票和活动时间。
- Produces: `evaluate_project(project_name) -> list[RiskFinding]`、`upsert_risks(project_name, findings) -> list[str]`、小时/每日风险扫描任务。

- [ ] **Step 1: 写延期、库存、回款和去重测试**

```python
from frappe.tests.utils import FrappeTestCase
import frappe

from autoflow_360.risk_engine.service import evaluate_project, upsert_risks
from autoflow_360.tests.factories import (
	make_overdue_project,
	make_project_with_supplier_eta_after_delivery,
	make_unpaid_project,
)


class TestRiskEngine(FrappeTestCase):
	def test_supplier_eta_after_delivery_is_high_risk(self):
		project = make_project_with_supplier_eta_after_delivery()
		findings = evaluate_project(project.name)
		finding = next(item for item in findings if item.rule_code == "SUPPLIER_DELAY")
		self.assertEqual(finding.level, "高")
		self.assertEqual(finding.reference_doctype, "Purchase Order")

	def test_repeated_scan_does_not_duplicate_open_risk(self):
		project = make_overdue_project()
		first = upsert_risks(project.name, evaluate_project(project.name))
		second = upsert_risks(project.name, evaluate_project(project.name))
		self.assertEqual(first, second)

	def test_rule_evidence_is_persisted(self):
		project = make_unpaid_project()
		names = upsert_risks(project.name, evaluate_project(project.name))
		risk = frappe.get_doc("Project Risk", names[0])
		self.assertTrue(risk.rule_inputs)
		self.assertTrue(risk.reference_name)
```

- [ ] **Step 2: 运行测试并确认风险引擎缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_risk_engine
```

Expected: `risk_engine.service` 无法导入。

- [ ] **Step 3: 创建风险对象和统一规则结果**

`Project Risk` 字段：

```text
customer_project Link Customer Project required
risk_type Data required
risk_level Select 低/中/高 required
title Data required
description Small Text required
rule_code Data
reference_doctype Link DocType
reference_name Dynamic Link reference_doctype
rule_inputs JSON read-only
deduplication_key Data unique
owner_user Link User
due_date Date
status Select 已发现/处理中/待验证/已关闭
resolved_at Datetime
verified_by Link User
```

```python
# autoflow_360/risk_engine/types.py
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class RiskFinding:
	rule_code: str
	risk_type: str
	level: str
	title: str
	description: str
	reference_doctype: str
	reference_name: str
	inputs: dict
	owner_user: str | None = None
	due_date: date | None = None
```

- [ ] **Step 4: 实现八条独立规则**

`rules.py` 必须导出：

```python
RULES = (
	find_overdue_milestones,
	find_pending_sample_feedback,
	find_quotation_expiry,
	find_stock_delivery_gap,
	find_supplier_delay,
	find_open_high_exceptions,
	find_overdue_receivables,
	find_inactive_project,
)
```

每个函数签名为：

```python
def find_supplier_delay(project) -> list[RiskFinding]:
	findings: list[RiskFinding] = []
	orders = frappe.get_all(
		"Purchase Order",
		filters={
			"custom_customer_project": project.name,
			"docstatus": 1,
			"status": ["not in", ["Completed", "Closed"]],
		},
		fields=["name", "custom_supplier_eta"],
	)
	for order in orders:
		if order.custom_supplier_eta and getdate(order.custom_supplier_eta) > getdate(project.customer_delivery_date):
			findings.append(
				RiskFinding(
					rule_code="SUPPLIER_DELAY",
					risk_type="供应商延期",
					level="高",
					title="供应商到货晚于客户交期",
					description=f"{order.name} 的预计到货日晚于客户要求交付日。",
					reference_doctype="Purchase Order",
					reference_name=order.name,
					inputs={
						"supplier_eta": str(order.custom_supplier_eta),
						"customer_delivery_date": str(project.customer_delivery_date),
					},
					owner_user=project.project_manager,
					due_date=project.customer_delivery_date,
				)
			)
	return findings
```

由于 `Business Exception` 在 Task 14 创建，Task 13 先提供兼容实现；Task 14 的集成测试验证对象存在后的行为：

```python
def find_open_high_exceptions(project) -> list[RiskFinding]:
	if not frappe.db.exists("DocType", "Business Exception"):
		return []
	return [
		RiskFinding(
			rule_code="HIGH_EXCEPTION_OPEN",
			risk_type="高风险异常",
			level="高",
			title="高风险异常尚未关闭",
			description=f"{row.name} 仍处于 {row.status}。",
			reference_doctype="Business Exception",
			reference_name=row.name,
			inputs={"status": row.status, "target_close_date": str(row.target_close_date or "")},
			owner_user=row.responsible_user or project.project_manager,
			due_date=row.target_close_date,
		)
		for row in frappe.get_all(
			"Business Exception",
			filters={
				"customer_project": project.name,
				"risk_level": "高",
				"status": ["not in", ["已关闭", "已取消"]],
			},
			fields=["name", "status", "target_close_date", "responsible_user"],
		)
	]
```

其余六条规则必须遵循相同返回结构，不能直接写数据库。

- [ ] **Step 5: 实现去重写入和调度**

```python
# autoflow_360/risk_engine/service.py
import hashlib
import json

import frappe

from autoflow_360.risk_engine.rules import RULES


def evaluate_project(project_name: str):
	project = frappe.get_doc("Customer Project", project_name)
	findings = []
	for rule in RULES:
		findings.extend(rule(project))
	return findings


def make_risk_key(project_name: str, finding) -> str:
	raw = "|".join(
		[
			project_name,
			finding.rule_code,
			finding.reference_doctype,
			finding.reference_name,
		]
	)
	return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def upsert_risks(project_name: str, findings) -> list[str]:
	names: list[str] = []
	active_keys: set[str] = set()
	for finding in findings:
		key = make_risk_key(project_name, finding)
		active_keys.add(key)
		existing = frappe.db.get_value(
			"Project Risk",
			{"deduplication_key": key, "status": ["!=", "已关闭"]},
			"name",
		)
		if existing:
			names.append(existing)
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Project Risk",
				"customer_project": project_name,
				"risk_type": finding.risk_type,
				"risk_level": finding.level,
				"title": finding.title,
				"description": finding.description,
				"rule_code": finding.rule_code,
				"reference_doctype": finding.reference_doctype,
				"reference_name": finding.reference_name,
				"rule_inputs": json.dumps(finding.inputs, ensure_ascii=False, sort_keys=True),
				"deduplication_key": key,
				"owner_user": finding.owner_user,
				"due_date": finding.due_date,
				"status": "已发现",
			}
		).insert(ignore_permissions=True)
		names.append(doc.name)
	for stale in frappe.get_all(
		"Project Risk",
		filters={
			"customer_project": project_name,
			"rule_code": ["is", "set"],
			"status": ["in", ["已发现", "处理中"]],
		},
		fields=["name", "deduplication_key"],
	):
		if stale.deduplication_key not in active_keys:
			frappe.db.set_value("Project Risk", stale.name, "status", "待验证")
	open_levels = frappe.get_all(
		"Project Risk",
		filters={
			"customer_project": project_name,
			"status": ["not in", ["已关闭"]],
		},
		pluck="risk_level",
	)
	rank = {"低": 1, "中": 2, "高": 3}
	overall = max(open_levels, key=lambda level: rank.get(level, 0), default="低")
	frappe.db.set_value("Customer Project", project_name, "overall_risk_level", overall)
	return names
```

`hooks.py` 增加：

```python
scheduler_events = {
	"hourly": ["autoflow_360.risk_engine.scheduled.scan_delivery_risks"],
	"daily": ["autoflow_360.risk_engine.scheduled.scan_daily_risks"],
}
```

```python
# autoflow_360/risk_engine/scheduled.py
import frappe

from autoflow_360.risk_engine.service import evaluate_project, upsert_risks


def _scan_active_projects() -> None:
	for project_name in frappe.get_all(
		"Customer Project",
		filters={"stage": ["not in", ["已结项", "失败", "取消"]]},
		pluck="name",
	):
		findings = evaluate_project(project_name)
		upsert_risks(project_name, findings)


def scan_delivery_risks() -> None:
	_scan_active_projects()


def scan_daily_risks() -> None:
	_scan_active_projects()
```

- [ ] **Step 6: 运行风险测试**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_risk_engine
```

Expected: 风险有来源、输入快照和唯一键；重复扫描不重复建单。

- [ ] **Step 7: 提交风险引擎**

```powershell
git add autoflow_360/autoflow_360/doctype/project_risk autoflow_360/risk_engine autoflow_360/tests/test_risk_engine.py autoflow_360/tests/factories.py autoflow_360/hooks.py
git commit -m "feat: add explainable project risk engine"
```

---

### Task 14: 实现业务异常、整改动作和独立验证

**Files:**

- Create: `autoflow_360/autoflow_360/doctype/corrective_action/corrective_action.json`
- Create: `autoflow_360/autoflow_360/doctype/business_exception/business_exception.json`
- Create: `autoflow_360/autoflow_360/doctype/business_exception/business_exception.py`
- Create: `autoflow_360/services/exception_workflow.py`
- Create: `autoflow_360/tests/test_exception_workflow.py`
- Modify: `autoflow_360/tests/factories.py`

**Interfaces:**

- Consumes: 客户项目和任意来源单据。
- Produces: `transition_exception(exception_name, target_status, evidence=None) -> str`、高风险关闭的独立验证门槛。

- [ ] **Step 1: 写状态跳跃、证据和独立验证失败测试**

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.risk_engine.service import evaluate_project
from autoflow_360.services.project_closure import get_closure_gaps
from autoflow_360.services.exception_workflow import transition_exception
from autoflow_360.tests.factories import make_business_exception, make_fulfilled_project


class TestExceptionWorkflow(FrappeTestCase):
	def test_exception_cannot_skip_root_cause(self):
		exception = make_business_exception(status="已分派")
		self.assertRaises(
			frappe.ValidationError,
			transition_exception,
			exception.name,
			"整改中",
		)

	def test_high_risk_creator_cannot_verify_own_exception(self):
		exception = make_business_exception(
			status="待验证",
			risk_level="高",
			raised_by=frappe.session.user,
		)
		self.assertRaises(
			frappe.PermissionError,
			transition_exception,
			exception.name,
			"已关闭",
			"evidence-file",
		)

	def test_close_requires_completed_actions_and_evidence(self):
		exception = make_business_exception(status="待验证", all_actions_complete=False)
		self.assertRaises(
			frappe.ValidationError,
			transition_exception,
			exception.name,
			"已关闭",
			None,
		)

	def test_open_high_exception_blocks_project_and_creates_risk(self):
		project = make_fulfilled_project(outstanding_amount=0)
		make_business_exception(project.name, risk_level="高", status="整改中")
		gaps = get_closure_gaps(project.name)
		self.assertIn("OPEN_HIGH_EXCEPTION", {gap.code for gap in gaps})
		findings = evaluate_project(project.name)
		self.assertIn("HIGH_EXCEPTION_OPEN", {finding.rule_code for finding in findings})
```

- [ ] **Step 2: 运行测试并确认异常服务缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_exception_workflow
```

Expected: `exception_workflow` 无法导入。

- [ ] **Step 3: 创建异常与整改模型**

`Business Exception` 字段：

```text
customer_project Link Customer Project required
exception_type Select 供应商延期/来料质量/库存差异/客户投诉/价格偏差/单据错误 required
risk_level Select 低/中/高 required
reference_doctype Link DocType required
reference_name Dynamic Link reference_doctype required
description Small Text required
impact Small Text required
raised_by Link User read-only
raised_at Datetime read-only
status Select 已发现/已分级/已分派/根因分析中/整改中/待验证/已关闭/已取消
responsible_department Data
responsible_user Link User
root_cause Long Text
target_close_date Date
actions Table Corrective Action
verification_evidence Attach
verified_by Link User read-only
verified_at Datetime read-only
cancellation_reason Small Text
```

`Corrective Action` 字段：

```text
action Data required
owner_user Link User required
due_date Date required
status Select 未开始/进行中/已完成 required
evidence Attach
completed_at Datetime
verification_result Small Text
```

- [ ] **Step 4: 实现严格相邻状态转换**

```python
# autoflow_360/services/exception_workflow.py
import frappe
from frappe import _
from frappe.utils import now_datetime

TRANSITIONS = {
	"已发现": {"已分级", "已取消"},
	"已分级": {"已分派", "已取消"},
	"已分派": {"根因分析中", "已取消"},
	"根因分析中": {"整改中", "已取消"},
	"整改中": {"待验证", "已取消"},
	"待验证": {"已关闭", "整改中"},
}


def transition_exception(
	exception_name: str,
	target_status: str,
	evidence: str | None = None,
) -> str:
	doc = frappe.get_doc("Business Exception", exception_name)
	doc.check_permission("write")
	if target_status not in TRANSITIONS.get(doc.status, set()):
		frappe.throw(_("Invalid exception transition from {0} to {1}.").format(doc.status, target_status))
	if target_status == "整改中" and not doc.root_cause:
		frappe.throw(_("Root cause is required before corrective action."))
	if target_status == "待验证":
		incomplete = [item for item in doc.actions if item.status != "已完成" or not item.evidence]
		if incomplete:
			frappe.throw(_("All corrective actions require completion evidence."))
	if target_status == "已关闭":
		if not evidence:
			frappe.throw(_("Verification evidence is required."))
		if doc.risk_level == "高" and doc.raised_by == frappe.session.user:
			raise frappe.PermissionError
		doc.verification_evidence = evidence
		doc.verified_by = frappe.session.user
		doc.verified_at = now_datetime()
	doc.status = target_status
	doc.save()
	return doc.name
```

- [ ] **Step 5: 运行异常测试**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_exception_workflow
```

Expected: 不能跳步；整改必须有证据；高风险异常由不同人员验证。

- [ ] **Step 6: 提交异常闭环**

```powershell
git add autoflow_360/autoflow_360/doctype/corrective_action autoflow_360/autoflow_360/doctype/business_exception autoflow_360/services/exception_workflow.py autoflow_360/tests/test_exception_workflow.py autoflow_360/tests/factories.py
git commit -m "feat: add auditable exception corrective-action loop"
```

---

### Task 15: 实现项目级、多公司和门户数据隔离

**Files:**

- Create: `autoflow_360/permissions/project.py`
- Create: `autoflow_360/tests/test_permissions.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/permissions/portal.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: 项目负责人、`Project Member`、Frappe User Permission、客户/供应商动态链接。
- Produces: `customer_project_query(user) -> str`、`customer_project_has_permission(doc, user, permission_type) -> bool | None`、统一门户对象校验。

- [ ] **Step 1: 写七角色、跨公司和门户隔离测试**

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.tests.factories import (
	add_company_user_permission,
	make_customer_portal_user,
	make_customer_project,
	make_customer_project_with_member,
	make_internal_user,
	make_over_limit_approval_request,
	make_project_for_company,
)

class TestPermissions(FrappeTestCase):
	def test_project_member_can_read_assigned_project_only(self):
		user = make_internal_user("project.member@example.invalid", ["AutoFlow Project Manager"])
		allowed = make_customer_project_with_member(user)
		blocked = make_customer_project_with_member("Administrator")
		frappe.set_user(user)
		names = {row.name for row in frappe.get_list("Customer Project", fields=["name"])}
		self.assertIn(allowed.name, names)
		self.assertNotIn(blocked.name, names)

	def test_company_user_permission_blocks_other_company(self):
		user = make_internal_user("finance.user@example.invalid", ["AutoFlow Finance"])
		add_company_user_permission(user, "_Test Company")
		other = make_project_for_company("_Test Company 2")
		frappe.set_user(user)
		self.assertFalse(frappe.has_permission("Customer Project", "read", other.name))

	def test_customer_portal_cannot_read_other_customer(self):
		user = make_customer_portal_user("_Test Customer")
		other = make_customer_project(customer="_Test Customer 2")
		frappe.set_user(user)
		self.assertFalse(frappe.has_permission("Customer Project", "read", other.name))

	def test_system_manager_is_not_automatic_business_approver(self):
		request = make_over_limit_approval_request()
		frappe.set_user("Administrator")
		self.assertRaises(frappe.PermissionError, request.approve, "Administrator")
```

- [ ] **Step 2: 运行测试并确认隔离尚未生效**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_permissions
```

Expected: 至少一个跨项目或跨公司读取测试失败。

- [ ] **Step 3: 实现列表查询条件**

```python
# autoflow_360/permissions/project.py
import frappe

INTERNAL_GLOBAL_READ_ROLES = {
	"AutoFlow Executive",
	"AutoFlow Administrator",
}


def customer_project_query(user: str | None = None) -> str:
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	roles = set(frappe.get_roles(user))
	if roles & INTERNAL_GLOBAL_READ_ROLES:
		return ""
	escaped_user = frappe.db.escape(user)
	member_projects = """
		SELECT parent
		FROM `tabProject Member`
		WHERE parenttype = 'Customer Project'
		  AND user = {user}
	""".format(user=escaped_user)
	return (
		f"(`tabCustomer Project`.`project_manager` = {escaped_user} "
		f"OR `tabCustomer Project`.`name` IN ({member_projects}))"
	)
```

- [ ] **Step 4: 实现单记录与门户权限**

```python
def customer_project_has_permission(
	doc,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool | None:
	user = user or frappe.session.user
	if user == "Administrator":
		return None
	roles = set(frappe.get_roles(user))
	allowed_companies = frappe.get_all(
		"User Permission",
		filters={
			"user": user,
			"allow": "Company",
		},
		pluck="for_value",
	)
	if allowed_companies and doc.company not in allowed_companies:
		return False
	if "AutoFlow Customer Portal" in roles:
		customer = get_customer_for_user(user)
		return bool(customer and doc.customer == customer and permission_type == "read")
	if roles & INTERNAL_GLOBAL_READ_ROLES:
		return None
	if doc.project_manager == user:
		return None
	return bool(
		frappe.db.exists(
			"Project Member",
			{"parent": doc.name, "parenttype": "Customer Project", "user": user},
		)
	)
```

公司隔离依赖 Frappe `User Permission`，测试中不能通过 `ignore_permissions=True` 绕过实际读取。

- [ ] **Step 5: 注册权限钩子并运行矩阵测试**

`hooks.py` 增加：

```python
permission_query_conditions = {
	"Customer Project": "autoflow_360.permissions.project.customer_project_query",
}

has_permission = {
	"Customer Project": "autoflow_360.permissions.project.customer_project_has_permission",
	"Supplier Quotation": "autoflow_360.permissions.portal.supplier_document_is_allowed",
	"Purchase Order": "autoflow_360.permissions.portal.supplier_document_is_allowed",
}
```

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_permissions
```

Expected: 七个内部角色、两个门户角色和公司限制全部符合矩阵。

- [ ] **Step 6: 提交权限隔离**

```powershell
git add autoflow_360/permissions autoflow_360/tests/test_permissions.py autoflow_360/tests/factories.py autoflow_360/hooks.py
git commit -m "feat: enforce project company and portal isolation"
```

---

### Task 16: 实现可插拔、可追溯、可降级的 AI 助手

**Files:**

- Create: `autoflow_360/autoflow_360/doctype/ai_source_reference/ai_source_reference.json`
- Create: `autoflow_360/autoflow_360/doctype/ai_analysis/ai_analysis.json`
- Create: `autoflow_360/autoflow_360/doctype/ai_analysis/ai_analysis.py`
- Create: `autoflow_360/ai/providers/base.py`
- Create: `autoflow_360/ai/providers/disabled.py`
- Create: `autoflow_360/ai/providers/openai_compatible.py`
- Create: `autoflow_360/ai/schemas.py`
- Create: `autoflow_360/ai/context_builder.py`
- Create: `autoflow_360/ai/audit.py`
- Create: `autoflow_360/ai/service.py`
- Create: `autoflow_360/api/analytics.py`
- Create: `autoflow_360/tests/test_ai_service.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: 当前用户有权限的项目、风险、异常、样品和业务单据。
- Produces: `analyze_project(project_name, analysis_type) -> str`，返回 `AI Analysis` 记录名；模型失败时返回状态为 `降级` 的记录。

- [ ] **Step 1: 写来源、越权、失败降级和无自动写入测试**

```python
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.ai.service import analyze_project
from autoflow_360.tests.factories import (
	make_customer_project,
	make_customer_project_with_member,
	make_internal_user,
	make_project_with_risk,
)


class TestAIService(FrappeTestCase):
	def test_analysis_contains_existing_source_records(self):
		project = make_project_with_risk()
		with patch("autoflow_360.ai.service.get_provider") as provider:
			provider.return_value.generate.return_value = {
				"summary": "存在供应商延期风险。",
				"risk_level": "高",
				"actions": [{"text": "确认替代交期", "owner_role": "AutoFlow Procurement"}],
				"sources": [{"doctype": "Project Risk", "name": project.risk_name}],
				"uncertainties": [],
			}
			name = analyze_project(project.name, "风险摘要")
		analysis = frappe.get_doc("AI Analysis", name)
		self.assertEqual(analysis.status, "成功")
		self.assertEqual(analysis.sources[0].reference_name, project.risk_name)

	def test_unknown_source_rejects_model_output(self):
		project = make_customer_project()
		with patch("autoflow_360.ai.service.get_provider") as provider:
			provider.return_value.generate.return_value = {
				"summary": "虚构结论",
				"risk_level": "高",
				"actions": [],
				"sources": [{"doctype": "Sales Order", "name": "FAKE-SO-0001"}],
				"uncertainties": [],
			}
			name = analyze_project(project.name, "风险摘要")
		self.assertEqual(frappe.db.get_value("AI Analysis", name, "status"), "降级")

	def test_provider_failure_does_not_change_business_documents(self):
		project = make_customer_project()
		before_stage = project.stage
		with patch("autoflow_360.ai.service.get_provider") as provider:
			provider.return_value.generate.side_effect = TimeoutError("synthetic timeout")
			name = analyze_project(project.name, "风险摘要")
		self.assertEqual(frappe.db.get_value("AI Analysis", name, "status"), "降级")
		self.assertEqual(frappe.db.get_value("Customer Project", project.name, "stage"), before_stage)

	def test_user_cannot_analyze_unreadable_project(self):
		project = make_customer_project_with_member("Administrator")
		frappe.set_user(make_internal_user("blocked.ai@example.invalid", ["AutoFlow Project Manager"]))
		self.assertRaises(frappe.PermissionError, analyze_project, project.name, "风险摘要")
```

- [ ] **Step 2: 运行测试并确认 AI 模块缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_ai_service
```

Expected: `autoflow_360.ai.service` 无法导入。

- [ ] **Step 3: 创建 AI 记录和输出类型**

`AI Analysis` 字段：

```text
customer_project Link Customer Project required
analysis_type Select 风险摘要/下一步行动/管理周报/根因草稿/供应商报价总结/结项复盘 required
requested_by Link User read-only
requested_at Datetime read-only
provider Data read-only
model Data read-only
prompt_version Data read-only
input_hash Data read-only
status Select 处理中/成功/降级/失败 read-only
output_json JSON read-only
display_text Long Text read-only
latency_ms Int read-only
error_code Data read-only
error_message Small Text read-only
sources Table AI Source Reference
adopted Check
user_revision Long Text
user_feedback Select 有帮助/部分有帮助/无帮助
```

`AI Source Reference` 字段：

```text
reference_doctype Link DocType required
reference_name Dynamic Link reference_doctype required
label Data required
```

```python
# autoflow_360/ai/schemas.py
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceReference:
	doctype: str
	name: str


@dataclass(frozen=True, slots=True)
class AIResult:
	summary: str
	risk_level: str
	actions: tuple[dict, ...]
	sources: tuple[SourceReference, ...]
	uncertainties: tuple[str, ...]
```

- [ ] **Step 4: 实现模型接口与兼容提供方**

```python
# autoflow_360/ai/providers/base.py
from typing import Protocol


class AIProvider(Protocol):
	name: str

	def generate(self, *, model: str, messages: list[dict], timeout_seconds: int) -> dict:
		...
```

```python
# autoflow_360/ai/providers/disabled.py
class DisabledProvider:
	name = "disabled"

	def generate(self, *, model: str, messages: list[dict], timeout_seconds: int) -> dict:
		raise RuntimeError("AI provider is disabled")
```

```python
# autoflow_360/ai/providers/openai_compatible.py
import json

import requests


class OpenAICompatibleProvider:
	name = "openai-compatible"

	def __init__(self, base_url: str, api_key: str):
		self.base_url = base_url.rstrip("/")
		self.api_key = api_key

	def generate(self, *, model: str, messages: list[dict], timeout_seconds: int) -> dict:
		response = requests.post(
			f"{self.base_url}/chat/completions",
			headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
			json={
				"model": model,
				"messages": messages,
				"temperature": 0,
				"response_format": {"type": "json_object"},
			},
			timeout=timeout_seconds,
		)
		response.raise_for_status()
		payload = response.json()
		content = payload["choices"][0]["message"]["content"]
		return json.loads(content)
```

实现时对响应缺字段、非 JSON、HTTP 错误、超时和限流分别映射安全错误码。

- [ ] **Step 5: 实现权限上下文、引用校验和审计**

```python
# autoflow_360/ai/context_builder.py
import frappe


def build_project_context(project_name: str) -> tuple[dict, set[tuple[str, str]]]:
	project = frappe.get_doc("Customer Project", project_name)
	if not project.has_permission("read"):
		raise frappe.PermissionError
	allowed: set[tuple[str, str]] = {("Customer Project", project.name)}
	risks = frappe.get_list(
		"Project Risk",
		filters={"customer_project": project.name},
		fields=["name", "risk_level", "title", "description", "reference_doctype", "reference_name", "status"],
	)
	for risk in risks:
		allowed.add(("Project Risk", risk.name))
		if risk.reference_doctype and risk.reference_name and frappe.has_permission(
			risk.reference_doctype,
			"read",
			risk.reference_name,
		):
			allowed.add((risk.reference_doctype, risk.reference_name))
	return (
		{
			"project": {
				"name": project.name,
				"stage": project.stage,
				"customer_delivery_date": str(project.customer_delivery_date),
				"overall_risk_level": project.overall_risk_level,
				"next_action": project.next_action,
			},
			"risks": risks,
		},
		allowed,
	)
```

`analyze_project()` 流程固定为：权限校验 → 构建最小上下文 → 记录输入哈希 → 调用提供方 → 解析结构 → 校验每个来源属于 `allowed` → 保存结果。任何失败都保存 `降级` 记录，但不修改正式业务对象。

```python
# autoflow_360/ai/service.py
import hashlib
import json
from time import perf_counter

import frappe
from frappe.utils import now_datetime

from autoflow_360.ai.context_builder import build_project_context
from autoflow_360.ai.providers.disabled import DisabledProvider
from autoflow_360.ai.providers.openai_compatible import OpenAICompatibleProvider

PROMPT_VERSION = "project-analysis-v1"


def get_provider(settings):
	if not settings.ai_enabled or settings.ai_provider == "Disabled":
		return DisabledProvider()
	if settings.ai_provider == "OpenAI Compatible":
		return OpenAICompatibleProvider(
			settings.ai_base_url,
			settings.get_password("ai_api_key"),
		)
	raise ValueError("Unsupported AI provider")


def analyze_project(project_name: str, analysis_type: str) -> str:
	context, allowed_sources = build_project_context(project_name)
	settings = frappe.get_single("AutoFlow Settings")
	input_json = json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
	analysis = frappe.get_doc(
		{
			"doctype": "AI Analysis",
			"customer_project": project_name,
			"analysis_type": analysis_type,
			"requested_by": frappe.session.user,
			"requested_at": now_datetime(),
			"provider": settings.ai_provider,
			"model": settings.ai_model,
			"prompt_version": PROMPT_VERSION,
			"input_hash": hashlib.sha256(input_json.encode("utf-8")).hexdigest(),
			"status": "处理中",
		}
	).insert()
	started = perf_counter()
	try:
		result = get_provider(settings).generate(
			model=settings.ai_model,
			messages=[
				{
					"role": "system",
					"content": (
						"仅根据提供的业务 JSON 生成分析。"
						"输出 JSON 字段必须为 summary、risk_level、actions、sources、uncertainties。"
					),
				},
				{"role": "user", "content": input_json},
			],
			timeout_seconds=30,
		)
		required = {"summary", "risk_level", "actions", "sources", "uncertainties"}
		if not isinstance(result, dict) or not required.issubset(result):
			raise ValueError("Invalid AI response schema")
		source_pairs = {
			(source.get("doctype"), source.get("name"))
			for source in result["sources"]
			if isinstance(source, dict)
		}
		if not source_pairs or not source_pairs.issubset(allowed_sources):
			raise ValueError("AI response contains missing or unauthorized sources")
		analysis.output_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
		analysis.display_text = result["summary"]
		for doctype, name in sorted(source_pairs):
			analysis.append(
				"sources",
				{
					"reference_doctype": doctype,
					"reference_name": name,
					"label": f"{doctype} {name}",
				},
			)
		analysis.status = "成功"
	except Exception as error:
		analysis.status = "降级"
		analysis.error_code = type(error).__name__
		analysis.error_message = "AI 暂时不可用，确定性风险结果仍然有效。"
	finally:
		analysis.latency_ms = int((perf_counter() - started) * 1000)
		analysis.save(ignore_permissions=True)
	return analysis.name


def generate_weekly_drafts() -> None:
	settings = frappe.get_single("AutoFlow Settings")
	if not settings.ai_enabled:
		return
	for project_name in frappe.get_all(
		"Customer Project",
		filters={"stage": ["not in", ["已结项", "失败", "取消"]]},
		pluck="name",
		limit_page_length=50,
	):
		frappe.enqueue(
			"autoflow_360.ai.service.analyze_project",
			queue="long",
			project_name=project_name,
			analysis_type="管理周报",
			enqueue_after_commit=True,
		)
```

- [ ] **Step 6: 注册周报后台任务并运行 AI 测试**

`hooks.py` 的 `scheduler_events` 增加：

```python
"weekly_long": ["autoflow_360.ai.service.generate_weekly_drafts"],
```

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost migrate
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_ai_service
```

Expected: 有效结果带来源；虚构来源和超时进入降级；项目状态不变。

- [ ] **Step 7: 提交 AI 助手**

```powershell
git add autoflow_360/autoflow_360/doctype/ai_source_reference autoflow_360/autoflow_360/doctype/ai_analysis autoflow_360/ai autoflow_360/api/analytics.py autoflow_360/tests/test_ai_service.py autoflow_360/tests/factories.py autoflow_360/hooks.py
git commit -m "feat: add traceable and fail-safe AI assistant"
```

---

### Task 17: 实现角色工作台、项目全景页和管理驾驶舱

**Files:**

- Create: `autoflow_360/autoflow_360/page/autoflow_workbench/autoflow_workbench.json`
- Create: `autoflow_360/autoflow_360/page/autoflow_workbench/autoflow_workbench.js`
- Create: `autoflow_360/autoflow_360/page/autoflow_workbench/autoflow_workbench.py`
- Create: `autoflow_360/autoflow_360/page/autoflow_cockpit/autoflow_cockpit.json`
- Create: `autoflow_360/autoflow_360/page/autoflow_cockpit/autoflow_cockpit.js`
- Create: `autoflow_360/autoflow_360/page/autoflow_cockpit/autoflow_cockpit.py`
- Create: `autoflow_360/public/css/autoflow.css`
- Create: `autoflow_360/tests/test_analytics_api.py`
- Modify: `autoflow_360/tests/factories.py`
- Modify: `autoflow_360/api/analytics.py`
- Modify: `autoflow_360/hooks.py`

**Interfaces:**

- Consumes: 当前用户角色、待办、项目、风险、异常、销售采购和财务汇总。
- Produces: `get_workbench_data() -> dict`、`get_management_cockpit(filters=None) -> dict`。

- [ ] **Step 1: 写工作台响应结构和下钻来源测试**

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.api.analytics import get_management_cockpit, get_workbench_data
from autoflow_360.tests.factories import make_customer_project_with_member, make_internal_user


class TestAnalyticsAPI(FrappeTestCase):
	def test_workbench_returns_actionable_sections(self):
		data = get_workbench_data()
		self.assertEqual(
			set(data),
			{"role", "approvals", "high_risks", "due_within_seven_days", "projects"},
		)
		for item in data["high_risks"]:
			self.assertTrue(item["doctype"])
			self.assertTrue(item["name"])
			self.assertTrue(item["route"])

	def test_cockpit_metric_has_definition_and_drilldown(self):
		data = get_management_cockpit({"company": "_Test Company"})
		for metric in data["metrics"]:
			self.assertTrue(metric["code"])
			self.assertTrue(metric["definition"])
			self.assertIn("value", metric)
			self.assertTrue(metric["drilldown"])

	def test_api_respects_current_user_permissions(self):
		hidden_project = make_customer_project_with_member("Administrator")
		frappe.set_user(make_internal_user("dashboard.user@example.invalid", ["AutoFlow Project Manager"]))
		data = get_workbench_data()
		self.assertNotIn(hidden_project.name, {row["name"] for row in data["projects"]})
```

- [ ] **Step 2: 运行测试并确认接口结构未实现**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_analytics_api
```

Expected: 接口缺失或返回字段不完整。

- [ ] **Step 3: 实现工作台接口**

```python
# autoflow_360/api/analytics.py
import frappe
from frappe.utils import add_days, nowdate


ROLE_PRIORITY = (
	"AutoFlow Executive",
	"AutoFlow Project Manager",
	"AutoFlow Sales Operations",
	"AutoFlow Procurement",
	"AutoFlow Warehouse",
	"AutoFlow Finance",
	"AutoFlow Administrator",
)


def resolve_primary_role(roles: list[str]) -> str:
	role_set = set(roles)
	return next((role for role in ROLE_PRIORITY if role in role_set), "Guest")


def get_user_approvals(user: str) -> list[dict]:
	rows = frappe.get_list(
		"AutoFlow Approval Request",
		filters={"status": "待审批"},
		fields=["name", "approval_type", "reference_doctype", "reference_name", "requested_by"],
		limit_page_length=20,
	)
	return [
		{
			**row,
			"route": f"/app/autoflow-approval-request/{row.name}",
		}
		for row in rows
		if row.requested_by != user
	]


def get_due_items(start_date: str, end_date: str) -> list[dict]:
	milestones = frappe.get_list(
		"Project Milestone",
		filters={
			"planned_date": ["between", [start_date, end_date]],
			"status": ["!=", "已完成"],
		},
		fields=["parent", "milestone_name", "planned_date", "owner_user"],
		limit_page_length=50,
	)
	return [
		{
			"doctype": "Customer Project",
			"name": item.parent,
			"title": item.milestone_name,
			"due_date": item.planned_date,
			"owner": item.owner_user,
			"route": f"/app/customer-project/{item.parent}",
		}
		for item in milestones
	]


@frappe.whitelist()
def get_workbench_data() -> dict:
	user = frappe.session.user
	roles = frappe.get_roles(user)
	projects = frappe.get_list(
		"Customer Project",
		fields=[
			"name",
			"project_name",
			"customer",
			"stage",
			"overall_risk_level",
			"next_action",
			"next_action_due_date",
		],
		limit_page_length=20,
		order_by="modified desc",
	)
	risks = frappe.get_list(
		"Project Risk",
		filters={"risk_level": "高", "status": ["!=", "已关闭"]},
		fields=["name", "title", "customer_project", "due_date"],
		limit_page_length=20,
	)
	return {
		"role": resolve_primary_role(roles),
		"approvals": get_user_approvals(user),
		"high_risks": [
			{
				"doctype": "Project Risk",
				"name": item.name,
				"title": item.title,
				"route": f"/app/project-risk/{item.name}",
			}
			for item in risks
		],
		"due_within_seven_days": get_due_items(nowdate(), add_days(nowdate(), 7)),
		"projects": projects,
	}


@frappe.whitelist()
def get_management_cockpit(filters: dict | str | None = None) -> dict:
	if "AutoFlow Executive" not in frappe.get_roles() and frappe.session.user != "Administrator":
		raise frappe.PermissionError
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	project_filters: dict = {}
	if filters.get("company"):
		project_filters["company"] = filters["company"]
	projects = frappe.get_list(
		"Customer Project",
		filters=project_filters,
		fields=["name", "stage", "overall_risk_level", "expected_amount"],
		limit_page_length=500,
	)
	high_risk = [row for row in projects if row.overall_risk_level == "高"]
	return {
		"filters": filters,
		"metrics": [
			{
				"code": "ACTIVE_PROJECTS",
				"label": "在途项目",
				"definition": "未结项、失败或取消的客户项目数量。",
				"value": sum(row.stage not in {"已结项", "失败", "取消"} for row in projects),
				"drilldown": "/app/customer-project",
			},
			{
				"code": "HIGH_RISK_PROJECTS",
				"label": "高风险项目",
				"definition": "总体风险等级为高且当前可读取的客户项目数量。",
				"value": len(high_risk),
				"drilldown": "/app/customer-project?overall_risk_level=高",
			},
		],
		"stage_distribution": {
			stage: sum(row.stage == stage for row in projects)
			for stage in sorted({row.stage for row in projects})
		},
	}
```

所有查询使用 `frappe.get_list()`；管理驾驶舱只有 `AutoFlow Executive` 或被授权角色可调用。

- [ ] **Step 4: 实现页面骨架和项目详情标签**

页面布局必须固定：

```text
左侧 220px：角色导航
顶部 64px：搜索、通知、快速新建、用户
主区 minmax(0, 7fr)：待办、项目、端到端流程、关联单据
右区 minmax(280px, 3fr)：高风险与 AI 助手
```

项目表单通过 `customer_project.js` 增加“概览、流程、关联单据、风险异常、AI 分析、操作记录”入口，并保持标准表单键盘和移动端可用性。

- [ ] **Step 5: 运行接口测试和页面构建**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_analytics_api
.\scripts\bench.ps1 build --app autoflow_360
```

Expected: 接口测试通过，前端构建无错误。

- [ ] **Step 6: 提交角色工作台**

```powershell
git add autoflow_360/autoflow_360/page autoflow_360/public/css/autoflow.css autoflow_360/api/analytics.py autoflow_360/tests/test_analytics_api.py autoflow_360/tests/factories.py autoflow_360/public/js/customer_project.js autoflow_360/hooks.py
git commit -m "feat: add role workbench and management cockpit"
```

---

### Task 18: 建立三条合成演示流程、端到端测试和性能基线

**Files:**

- Create: `autoflow_360/demo/__init__.py`
- Create: `autoflow_360/demo/seed.py`
- Create: `autoflow_360/tests/test_demo_seed.py`
- Create: `tests/e2e/package.json`
- Create: `tests/e2e/playwright.config.js`
- Create: `tests/e2e/normal-project.spec.js`
- Create: `tests/e2e/supplier-delay.spec.js`
- Create: `tests/e2e/resample.spec.js`
- Create: `tests/performance/generate_scale.py`
- Create: `tests/performance/measure.py`
- Create: `scripts/seed-demo.ps1`

**Interfaces:**

- Consumes: 全部已实现业务服务。
- Produces: `seed_demo_data(reset=False) -> dict`、三条稳定演示项目、可重复性能数据和浏览器验收报告。

- [ ] **Step 1: 写合成数据幂等和真实性边界测试**

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.demo.seed import seed_demo_data


class TestDemoSeed(FrappeTestCase):
	def test_seed_is_idempotent_and_creates_three_scenarios(self):
		first = seed_demo_data()
		second = seed_demo_data()
		self.assertEqual(first, second)
		self.assertEqual(set(first), {"normal", "supplier_delay", "resample"})
		self.assertEqual(
			frappe.db.count("Customer Project", {"demo_scenario": ["is", "set"]}),
			3,
		)

	def test_demo_records_are_marked_synthetic(self):
		result = seed_demo_data()
		for project_name in result.values():
			project = frappe.get_doc("Customer Project", project_name)
			self.assertTrue(project.is_demo)
			self.assertIn("合成", project.data_classification)
```

- [ ] **Step 2: 运行测试并确认演示模块缺失**

Run:

```powershell
.\scripts\bench.ps1 --site autoflow.localhost run-tests --module autoflow_360.tests.test_demo_seed
```

Expected: `autoflow_360.demo.seed` 无法导入。

- [ ] **Step 3: 实现固定业务键和三条场景**

```python
# autoflow_360/demo/seed.py
import frappe

SCENARIO_KEYS = {
	"normal": "DEMO-NORMAL-001",
	"supplier_delay": "DEMO-DELAY-001",
	"resample": "DEMO-RESAMPLE-001",
}


def seed_demo_data(reset: bool = False) -> dict[str, str]:
	if reset:
		_reset_demo_records()
	results: dict[str, str] = {}
	for scenario, key in SCENARIO_KEYS.items():
		existing = frappe.db.get_value("Customer Project", {"demo_key": key}, "name")
		if existing:
			results[scenario] = existing
			continue
		if scenario == "normal":
			results[scenario] = _create_normal_project(key)
		elif scenario == "supplier_delay":
			results[scenario] = _create_supplier_delay_project(key)
		else:
			results[scenario] = _create_resample_project(key)
	return results
```

三个内部函数必须调用正式服务创建单据，不得直接把最终状态写入数据库。`reset=True` 只允许删除 `is_demo=1` 且 `demo_key` 属于固定集合的记录，删除前打印精确目标并要求交互确认；自动测试通过事务回滚，不执行真实删除。

- [ ] **Step 4: 创建三条浏览器验收脚本**

```javascript
// tests/e2e/normal-project.spec.js
const { test, expect } = require("@playwright/test");

test("normal project closes after delivery invoice and payment", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("Administrator");
  await page.getByLabel("Password").fill(process.env.AUTOFLOW_E2E_PASSWORD);
  await page.getByRole("button", { name: /login/i }).click();
  await page.goto("/app/autoflow-workbench");
  await page.getByText("DEMO-NORMAL-001").click();
  await expect(page.getByText("已结项")).toBeVisible();
  await page.getByRole("tab", { name: "关联单据" }).click();
  for (const label of ["销售订单", "采购订单", "交货单", "销售发票", "收款记录"]) {
    await expect(page.getByText(label)).toBeVisible();
  }
});
```

`supplier-delay.spec.js` 断言采购延期风险、异常、整改证据和关闭状态；`resample.spec.js` 断言第一轮拒绝、第二轮关联和最终认可。

- [ ] **Step 5: 建立性能数据与测量输出**

`generate_scale.py` 创建：

```text
200 Customer Project
1,000 Sample Request / Customer Feedback
500 Sales Order / Purchase Order
5,000 Project Risk / Business Exception / Version
```

`measure.py` 对项目列表、项目详情、风险扫描和周报任务各执行一次预热与十次正式测量，输出 `docs/test-report/performance.json`，包含环境版本、记录数、P50、P95 和最大耗时。

`scripts/seed-demo.ps1` 内容：

```powershell
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "bench.ps1") `
    --site autoflow.localhost execute autoflow_360.demo.seed.seed_demo_data
if ($LASTEXITCODE -ne 0) {
    throw "演示数据初始化失败。"
}
```

- [ ] **Step 6: 运行演示、端到端和性能验证**

Run:

```powershell
.\scripts\seed-demo.ps1
Set-Location tests\e2e
npm.cmd install
npx.cmd playwright install chromium
npx.cmd playwright test
Set-Location ..\..
.\scripts\bench.ps1 --site autoflow.localhost execute tests.performance.generate_scale.run
.\scripts\bench.ps1 --site autoflow.localhost execute tests.performance.measure.run
```

Expected: 三条端到端测试通过；性能报告包含真实环境和实际测量值。

- [ ] **Step 7: 提交演示和质量基线**

```powershell
git add autoflow_360/demo autoflow_360/tests/test_demo_seed.py tests/e2e tests/performance scripts/seed-demo.ps1 docs/test-report/performance.json
git commit -m "test: add end-to-end demo scenarios and performance baseline"
```

---

### Task 19: 建立持续集成、安全检查、生产镜像、免费部署和恢复演练

**Files:**

- Create: `.github/workflows/static.yml`
- Create: `.github/workflows/integration.yml`
- Create: `.github/workflows/build-image.yml`
- Create: `deploy/apps.production.json`
- Create: `deploy/oracle/compose.env.example`
- Create: `deploy/oracle/deploy.sh`
- Create: `deploy/oracle/backup.sh`
- Create: `deploy/oracle/restore-check.sh`
- Create: `scripts/start-tunnel.ps1`
- Create: `scripts/verify-backup.ps1`
- Create: `docs/deployment/oracle-always-free.md`
- Create: `docs/deployment/cloudflare-tunnel.md`
- Create: `docs/deployment/backup-and-restore.md`
- Create: `docs/security/threat-model.md`
- Create: `tests/static/test_secret_hygiene.py`

**Interfaces:**

- Consumes: 已推送的 AutoFlow 360 GitHub 仓库 URL、官方 frappe_docker 构建流程。
- Produces: 多架构自定义镜像、可复现生产 Compose、备份恢复证据和零月租演示路径。

- [ ] **Step 1: 写密钥卫生和生产应用锁定测试**

```python
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SecretHygieneTest(unittest.TestCase):
    def test_production_apps_include_all_required_apps(self):
        apps = json.loads((ROOT / "deploy" / "apps.production.json").read_text(encoding="utf-8"))
        urls = {item["url"] for item in apps}
        self.assertIn("https://github.com/frappe/erpnext", urls)
        self.assertIn("https://github.com/frappe/crm", urls)
        self.assertTrue(any(url.endswith("/autoflow-360") for url in urls))

    def test_tracked_text_contains_no_common_secret_patterns(self):
        forbidden = re.compile(r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|BEGIN PRIVATE KEY)")
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or ".runtime" in path.parts:
                continue
            if path.suffix.lower() not in {".py", ".js", ".json", ".yaml", ".yml", ".md", ".ps1", ".sh", ".env"}:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            self.assertIsNone(forbidden.search(content), str(path))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行静态测试并确认生产配置缺失**

Run:

```powershell
python -m unittest tests.static.test_secret_hygiene -v
```

Expected: `deploy/apps.production.json` 缺失。

- [ ] **Step 3: 固定生产应用并安全构建镜像**

`deploy/apps.production.json` 使用正式仓库 URL：

```json
[
  {
    "url": "https://github.com/frappe/erpnext",
    "branch": "version-16"
  },
  {
    "url": "https://github.com/frappe/crm",
    "branch": "main"
  },
  {
    "url": "https://github.com/JBX123159/autoflow-360",
    "branch": "codex/autoflow-360"
  }
]
```

镜像工作流必须使用 BuildKit secret：

```yaml
- name: Build custom Frappe image
  run: |
    git clone --depth 1 https://github.com/frappe/frappe_docker .runtime/frappe_docker
    cp deploy/apps.production.json .runtime/frappe_docker/apps.json
    cd .runtime/frappe_docker
    docker buildx build \
      --platform linux/amd64,linux/arm64 \
      --build-arg FRAPPE_PATH=https://github.com/frappe/frappe \
      --build-arg FRAPPE_BRANCH=version-16 \
      --secret id=apps_json,src=apps.json \
      --file images/layered/Containerfile \
      --tag ghcr.io/jbx123159/autoflow-360:${GITHUB_SHA} \
      --push .
```

禁止把 `apps.json` 作为普通 build argument 传入镜像历史。

- [ ] **Step 4: 建立静态和集成持续集成**

`static.yml` 执行：

```yaml
- run: python -m unittest discover -s tests/static -v
- run: python -m compileall -q autoflow_360
- run: git diff --check
```

`integration.yml` 在 Ubuntu runner 中：

1. 克隆 `frappe_docker`。
2. 使用 `version-16`、ERPNext `version-16` 和 CRM `main` 创建测试站点。
3. 安装当前提交的 `autoflow_360`。
4. 运行 `bench --site autoflow.test run-tests --app autoflow_360`。
5. 启动 Web 服务并运行 Playwright 三条流程。
6. 上传 JUnit、Playwright 和性能结果，失败时上传安全日志。

- [ ] **Step 5: 创建 Oracle ARM64 免费部署脚本**

```bash
#!/usr/bin/env bash
# deploy/oracle/deploy.sh
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runtime_dir="${project_dir}/.runtime/frappe_docker"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker 未安装。" >&2
  exit 1
fi
if [[ ! -d "${runtime_dir}" ]]; then
  git clone --depth 1 https://github.com/frappe/frappe_docker "${runtime_dir}"
fi

cd "${runtime_dir}"
docker compose \
  --env-file "${project_dir}/deploy/oracle/compose.env" \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.https.yaml \
  config > "${project_dir}/deploy/oracle/compose.generated.yaml"

docker compose \
  --env-file "${project_dir}/deploy/oracle/compose.env" \
  -f "${project_dir}/deploy/oracle/compose.generated.yaml" \
  up -d
```

脚本使用官方 Compose 与覆盖文件，不复制或修改上游核心文件。`compose.env` 不提交。

- [ ] **Step 6: 实现 Cloudflare Tunnel 免费临时公网演示入口**

```powershell
# scripts/start-tunnel.ps1
$ErrorActionPreference = "Stop"
$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($null -eq $cloudflared) {
    throw "未安装 cloudflared。请按 docs/deployment/cloudflare-tunnel.md 安装官方客户端。"
}

$healthUrl = "http://autoflow.localhost:8000/api/method/ping"
try {
    $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 10
} catch {
    throw "本地 AutoFlow 360 尚未运行：$($_.Exception.Message)"
}
if ($response.StatusCode -ne 200) {
    throw "本地健康检查失败，HTTP 状态：$($response.StatusCode)"
}

Write-Host "正在创建临时 Quick Tunnel；此地址仅用于面试演示，不承诺可用性。"
& $cloudflared.Source tunnel --url "http://autoflow.localhost:8000"
exit $LASTEXITCODE
```

`cloudflare-tunnel.md` 同时说明：Quick Tunnel 没有服务等级保证；长期在线需使用命名 Tunnel 和自有域名，但不作为免费验收前提。

- [ ] **Step 7: 实现备份和恢复演练**

`backup.sh` 执行 `bench --site "$SITE_NAME" backup --with-files --compress` 并输出 SHA-256；`restore-check.sh` 在独立临时站点恢复最近备份，运行 `migrate`、`list-apps` 和最小读取测试，成功后删除仅由脚本创建的临时站点。

Run:

```powershell
.\scripts\verify-backup.ps1
```

Expected: 输出备份文件哈希、临时恢复站点和 `RESTORE_CHECK_PASSED`。

- [ ] **Step 8: 完成威胁模型和密钥检查**

威胁模型必须覆盖：

- 客户/供应商横向越权。
- 公司间数据泄露。
- AI 上下文越权和提示注入。
- 附件路径、类型和大小滥用。
- 重复提交和并发审批。
- 密钥、令牌和日志泄露。
- 供应链依赖与镜像来源。
- 备份未加密或恢复不可用。

Run:

```powershell
python -m unittest tests.static.test_secret_hygiene -v
git grep -n -E "sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|BEGIN PRIVATE KEY"
```

Expected: 单元测试通过；`git grep` 无结果。

- [ ] **Step 9: 提交交付与安全能力**

```powershell
git add .github/workflows deploy scripts/start-tunnel.ps1 scripts/verify-backup.ps1 docs/deployment docs/security tests/static/test_secret_hygiene.py
git commit -m "build: add CI secure images free deployment and restore checks"
```

---

### Task 20: 完成用户文档、测试报告、求职材料和 GitHub 发布

**Files:**

- Create: `docs/architecture/system-context.md`
- Create: `docs/architecture/data-model.md`
- Create: `docs/architecture/business-flow.md`
- Create: `docs/user-guide/sales-and-project.md`
- Create: `docs/user-guide/procurement-and-delivery.md`
- Create: `docs/user-guide/customer-portal.md`
- Create: `docs/user-guide/supplier-portal.md`
- Create: `docs/user-guide/administrator.md`
- Create: `docs/test-report/acceptance.md`
- Create: `docs/test-report/known-limitations.md`
- Create: `docs/interview/resume-project.md`
- Create: `docs/interview/three-minute-pitch.md`
- Create: `docs/interview/questions-and-answers.md`
- Create: `docs/interview/personal-contribution.md`
- Create: `docs/demo-script.md`
- Create: `CHANGELOG.md`
- Create: `tests/static/test_delivery_artifacts.py`
- Modify: `deploy/apps.production.json`
- Modify: `README.md`

**Interfaces:**

- Consumes: 实际测试结果、部署地址、截图、提交历史和完成功能。
- Produces: 招聘方可验证的完整证据链、`v1.0.0` 发布候选和公开 GitHub 项目。

- [ ] **Step 1: 写交付物完整性测试**

```python
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DeliveryArtifactTest(unittest.TestCase):
    def test_recruitment_and_user_documents_exist(self):
        required = (
            "docs/architecture/system-context.md",
            "docs/architecture/data-model.md",
            "docs/architecture/business-flow.md",
            "docs/user-guide/sales-and-project.md",
            "docs/user-guide/procurement-and-delivery.md",
            "docs/user-guide/customer-portal.md",
            "docs/user-guide/supplier-portal.md",
            "docs/user-guide/administrator.md",
            "docs/test-report/acceptance.md",
            "docs/test-report/known-limitations.md",
            "docs/interview/resume-project.md",
            "docs/interview/three-minute-pitch.md",
            "docs/interview/questions-and-answers.md",
            "docs/interview/personal-contribution.md",
            "docs/demo-script.md",
            "CHANGELOG.md",
        )
        for relative_path in required:
            path = ROOT / relative_path
            self.assertTrue(path.is_file(), relative_path)
            self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 100, relative_path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认交付文档缺失**

Run:

```powershell
python -m unittest tests.static.test_delivery_artifacts -v
```

Expected: 尚未创建的用户指南或求职文档导致失败。

- [ ] **Step 3: 写基于证据的架构、用户和验收文档**

文档必须遵守：

- 每条功能对应实际页面、服务、测试或单据。
- 截图只展示合成数据。
- 性能数字来自 `performance.json`。
- 测试通过率来自当前测试输出。
- 已知限制明确列出，不把免费云资源描述为永久保证。
- 明确区分上游能力和 AutoFlow 360 自主新增能力。

验收报告表格固定列：

```markdown
| 需求 | 实现证据 | 测试证据 | 状态 | 说明 |
| --- | --- | --- | --- | --- |
| 商机到项目幂等转换 | `services/deal_conversion.py` | `test_deal_conversion.py` | 通过/失败 | 实际结果 |
```

- [ ] **Step 4: 写真实可面试的个人项目叙事**

`resume-project.md` 必须包含一版 70 到 100 字简历描述和三条贡献点，禁止写未实测用户数、营收或企业采用结果。

`three-minute-pitch.md` 固定结构：

1. 为什么选择汽车客户项目与供应链协同。
2. 为什么复用 Frappe CRM/ERPNext 而不是重复造轮子。
3. 完整业务闭环和最难的三项工程问题。
4. 权限、异常、AI 和部署如何保证可信。
5. 实际测试结果、局限和下一步。

`personal-contribution.md` 按“上游已有、本人设计、本人实现、工具辅助、尚未完成”五栏记录。

- [ ] **Step 5: 执行全量验收**

Run:

```powershell
python -m unittest discover -s tests/static -v
.\scripts\run-tests.ps1
Set-Location tests\e2e
npx.cmd playwright test
Set-Location ..\..
.\scripts\verify-backup.ps1
git diff --check
git status --short
```

Expected:

- 静态测试全部通过。
- Frappe 业务测试全部通过。
- 三条浏览器流程全部通过。
- 恢复演练输出 `RESTORE_CHECK_PASSED`。
- `git diff --check` 无输出。
- 仅存在本任务准备提交的文件。

- [ ] **Step 6: 完成 README、演示视频和截图索引**

README 必须提供：

- 一分钟项目概览。
- Mermaid 业务闭环图。
- 自主新增能力对照表。
- 三条演示账号和路径。
- 本地安装、测试、备份和免费部署入口。
- 截图、三到五分钟演示视频和在线地址。
- 许可证、来源、隐私和已知限制。

演示视频按 `docs/demo-script.md` 录制，依次展示正常项目、供应商延期和重新打样。

- [ ] **Step 7: 切换生产应用引用并提交交付材料**

将 `deploy/apps.production.json` 中 AutoFlow 360 的分支从 `codex/autoflow-360` 精确改为 `main`，然后运行：

```powershell
git add README.md CHANGELOG.md docs tests/static/test_delivery_artifacts.py deploy/apps.production.json
git commit -m "docs: complete AutoFlow 360 delivery and interview evidence"
```

- [ ] **Step 8: 推送、创建拉取请求、合并并标记发布候选**

Run:

```powershell
git push -u origin codex/autoflow-360
gh pr create `
  --base main `
  --head codex/autoflow-360 `
  --title "feat: deliver AutoFlow 360 end-to-end platform" `
  --body-file docs/test-report/acceptance.md
gh pr checks --watch
gh pr merge --merge --delete-branch
git switch main
git pull --ff-only origin main
git tag -a v1.0.0-rc1 -m "AutoFlow 360 v1.0.0 release candidate"
git push origin v1.0.0-rc1
```

Expected: 拉取请求检查全部通过并合并，`main` 指向通过验收的提交，`v1.0.0-rc1` 标签触发多架构镜像构建。正式 `v1.0.0` 只在发布候选部署验证后创建。

---

## 21. 规格覆盖自审

| 产品规格 | 实施任务 | 主要证据 |
| --- | --- | --- |
| 开源基座、许可证和真实性边界 | 1、2、19、20 | README、NOTICE、LICENSE、镜像配置、贡献清单 |
| 七个内部角色和两个门户角色 | 4、10、15 | 角色安装、权限矩阵测试 |
| CRM 商机到客户项目 | 5、6 | 客户项目状态机、幂等转换测试 |
| 样品、检验、反馈和重新打样 | 7 | 样品服务、客户门户、浏览器流程 |
| 报价、审批和销售订单 | 8 | 报价钩子、审批对象、转换测试 |
| 订单、库存缺口和物料需求 | 9 | 物料规划服务和缺口测试 |
| 询价、供应商报价和采购订单 | 10 | 采购服务和供应商门户 |
| 收货、库存、交付和签收 | 11 | 库存提交校验和客户签收 |
| 开票、回款和结项 | 12 | 结项缺口服务和严格门槛测试 |
| 八类确定性风险 | 13 | 风险规则、来源快照和去重 |
| 异常、根因、整改、证据和验证 | 14 | 异常状态机和独立验证 |
| 公司、项目、门户和 AI 权限 | 15、16 | 权限矩阵与 AI 越权测试 |
| AI 摘要、建议、引用、审计和降级 | 16 | AI Analysis、引用校验、模拟失败测试 |
| 角色工作台和管理驾驶舱 | 17 | 工作台 API、指标口径和下钻 |
| 后台风险和周报任务 | 13、16 | Scheduler hooks 与任务测试 |
| 三条合成演示业务 | 18 | 幂等数据脚本和 Playwright |
| 目标规模性能验证 | 18 | 固定记录数和实际性能 JSON |
| Docker、免费部署、备份恢复 | 3、19 | 本地环境、ARM64 镜像、恢复演练 |
| 安全与可观测性 | 13、16、19 | 审计、威胁模型、密钥扫描 |
| GitHub、文档和求职包装 | 20 | CI、验收报告、演示、简历和面试材料 |

自审结论：

- 所有产品规格主流程均映射到至少一个实现任务和一个验证证据。
- 标准 ERPNext 财务逻辑不被重写，只增加项目关联、校验和结项汇总。
- AI 依赖位于业务闭环之外，失败不会阻止核心业务。
- 免费部署包含 Oracle ARM64 和本地 Tunnel 两条路径，未把免费容量写成永久承诺。
- 所有性能、测试和业务效果数字均要求实际测量后填写。

## 22. 执行检查点

实施按以下检查点推进：

1. Task 1–3：仓库、应用包和完整站点可复现。
2. Task 4–7：角色、客户项目和样品闭环可独立演示。
3. Task 8–12：销售、采购、库存、交付、开票和回款闭环可运行。
4. Task 13–17：风险、异常、权限、AI 和工作台可验证。
5. Task 18–20：三条演示、性能、安全、免费部署和求职证据完整。

每个检查点结束时必须重新运行累计测试，不使用后续任务掩盖前一阶段失败。

## 23. 官方工程依据

- Frappe App 创建与目录结构：https://docs.frappe.io/framework/user/en/tutorial/create-an-app
- Frappe Hooks、权限和调度：https://docs.frappe.io/framework/user/en/python-api/hooks
- Frappe 测试：https://docs.frappe.io/framework/user/en/testing
- ERPNext v16：https://github.com/frappe/erpnext/tree/version-16
- Frappe CRM v1 兼容矩阵：https://github.com/frappe/crm
- frappe_docker 自定义镜像：https://github.com/frappe/frappe_docker/blob/main/docs/02-setup/02-build-setup.md
- frappe_docker 开发环境：https://github.com/frappe/frappe_docker/blob/main/docs/05-development/01-development.md
