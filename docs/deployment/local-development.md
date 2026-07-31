# 本地开发环境

## 环境范围

本方案使用官方 `frappe_docker` 开发容器建立 AutoFlow 360 的本地环境，固定采用：

- Frappe Framework `version-16`
- ERPNext `version-16`
- Frappe CRM `main`
- Python 3.14.x
- Node 24
- MariaDB 11.8 与 Redis

`deploy/container-lock.json` 进一步把 Frappe Bench、MariaDB 和 Redis 镜像固定到实际验证过的 `sha256` 摘要；Compose 标签只描述兼容线，实际运行不会悄悄拉取同名标签的新镜像。

开始前需要安装 WSL2 Ubuntu。Docker Engine 23 或更高版本与 Docker Compose v2 可以安装在 Windows，也可以直接安装在 WSL2 Ubuntu 内；脚本优先使用可用的 Windows Docker，否则自动调用 `AUTOFLOW_WSL_DISTRO` 指定发行版中的 Docker 和 Git，不依赖 Docker Desktop。Docker 至少分配 4 GB 内存。脚本兼容 Windows PowerShell 5.1，仓库路径可以包含中文和空格。

## 首次初始化

在仓库根目录执行：

```powershell
Copy-Item deploy/env.example .env
```

打开 `.env`，把 `AUTOFLOW_ADMIN_PASSWORD` 改成至少 12 个字符的本机专用密码。如果 WSL 发行版不叫 `Ubuntu`，同步修改 `AUTOFLOW_WSL_DISTRO`。不要提交 `.env`。配置文件只接受 `AUTOFLOW_SITE`、`AUTOFLOW_ADMIN_PASSWORD`、`AUTOFLOW_RUNTIME`、`AUTOFLOW_WSL_DISTRO` 四项；重复项、未知项、错误格式、换行或 NUL 字符会被拒绝，脚本不会使用 `Invoke-Expression` 执行配置内容。

然后运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\bootstrap-dev.ps1
.\scripts\bench.ps1 --site autoflow.localhost list-apps
```

第二条命令应输出 `frappe`、`erpnext`、`crm` 和 `autoflow_360`。自定义应用通过符号链接使用当前仓库，不会复制成另一份源码；修改本地文件后容器内立即可见。

首次安装需要克隆并安装四个应用。脚本把 Bench、Python 环境、Node 依赖和站点文件保存在 Docker 原生卷 `autoflow-360-bench-data`，避免 OneDrive/Windows 挂载盘的 9P 文件系统让迁移和测试长时间卡住。源码仓库仍以只读边界和符号链接挂载，修改 AutoFlow 360 代码后容器内立即可见。

如果检测到旧版脚本在 `.runtime/frappe_docker/development` 中创建过 Bench，首次升级会先停止旧 Frappe 容器，把该目录复制到原生卷，然后保留原目录作为恢复备份；复制中断后重跑会继续覆盖复制，不会删除源目录。首次复制和干净安装仍可能持续较长时间，不要因为终端暂时没有新输出就强制结束。

原生卷内同时保存项目绝对路径哈希、站点名和格式版本组成的所有权标记。其他仓库副本或不同站点即使碰到同名卷也会被明确拒绝，不会直接复用里面的数据。缺少标记的非空同名卷也不会被直接认领：只有卷为空，或卷内站点配置与当前项目保留的旧站点配置哈希完全一致时，脚本才允许继续。后一种情况会重新覆盖复制完整旧 Bench，以恢复可能中断的迁移，然后才写入所有权和就绪标记。

脚本先从官方仓库取得 `deploy/upstream-lock.json` 指定的精确提交，在本地缓存建立 `autoflow-lock` 分支，再让官方安装器只从这些本地锁定分支建立 Bench 和站点。安装完成后还会把应用 origin 恢复为官方地址并再次校验提交。锁定提交发生变化时，脚本会重装上游 Python/Node 依赖并重建资源；干净机器不会执行移动分支新 HEAD 中的安装代码。

使用 WSL Docker 时，脚本先把 `C:\...` 规范化为 `C:/...`，再以独立参数调用 `wslpath -a`，从而安全处理中文和空格路径。克隆上游也使用同一个 WSL 发行版内的 Git，避免 Windows Git 网络栈与 WSL Docker 混用。

启动开发服务并保持当前终端运行：

```powershell
.\scripts\bench.ps1 start
```

浏览器访问 `http://autoflow.localhost:8000`，用户名为 `Administrator`，密码是 `.env` 中的 `AUTOFLOW_ADMIN_PASSWORD`。

`.env` 中的管理员密码只用于本机开发，不能复用个人账号或生产密码。脚本把它作为容器环境变量传入，因此有权限查看本机进程环境的管理员可能在执行期间看到它。首次建站命令只使用一次性随机密码；应用随后从进程环境读取 `.env` 密码并同步，不把真实密码放进 Bench 命令参数。脚本还会把 Bench 日志中的一次性密码替换为 `<redacted>`。

每次运行 `bootstrap-dev.ps1` 都会把现有站点的 `Administrator` 密码同步为 `.env` 当前值，并注销已有会话；需要轮换时先修改 `.env`，再重跑初始化脚本。共享电脑上应在首次初始化后立即完成这一步。

部分 Windows/WSL 组合会在最后一个 `wsl.exe` 客户端退出后回收 WSL 实例，并随之停止 WSL 内的 Docker。开发期间请保持运行 `bench.ps1 start` 的终端开启；如果所有容器突然停止，重新启动 WSL Docker 后再运行启动命令。

## 数据库口令边界

官方 `frappe_docker` 的 `devcontainer-example` 和当前 `development/installer.py` 都把 MariaDB root 密码固定为 `123`。AutoFlow 360 不提供一个实际无效的“可配置数据库 root 密码”选项。

这个固定口令仅限本机隔离开发容器，不能对公网暴露数据库端口。生产环境禁止复用此开发 Compose、固定口令或示例管理员密码；生产部署必须使用独立密钥、最小权限和受控网络。

## 常用命令

```powershell
# 查看已安装应用
.\scripts\bench.ps1 --site autoflow.localhost list-apps

# 执行应用测试
# 先结束另一个终端中正在运行的 bench.ps1 start
.\scripts\run-tests.ps1

# 查看迁移状态
.\scripts\bench.ps1 --site autoflow.localhost migrate
```

`bootstrap-dev.ps1` 可以重复运行：它不会覆盖已有运行目录，不会拉取并悄悄改变已锁定的上游版本，也不会覆盖指向其他目录的 `apps/autoflow_360`。脚本会拒绝带有受跟踪文件改动的上游仓库；`frappe_docker/.devcontainer` 是生成目录，每次运行都会从当前锁定提交的 `devcontainer-example` 安全刷新，再重新生成本机挂载覆盖文件。

如果进程恰好在 Bench 基础目录尚未完整生成时中断，脚本会识别缺少 `env/bin/python`、`sites/apps.txt` 或 `apps/frappe` 的状态并拒绝覆盖。此时先备份 `autoflow-360-bench-data` 卷，再决定恢复或重建；不要直接删除未知卷。站点已生成、仅后续迁移中断时可以直接重跑。

`run-tests.ps1` 会为当前本地站点启用 Frappe 测试开关，然后只运行 `autoflow_360` 应用测试。该开关是开发环境配置，不应照搬到生产站点。
测试会短暂修改站点调度器状态；运行前应先结束 `bench.ps1 start`，避免 Web、调度器或残留测试事务与测试准备阶段争用数据库锁。如果看到 `Lock wait timeout exceeded`，结束开发服务和残留测试进程，等待事务释放后再单独重跑。

## 常见问题

- **提示管理员密码仍是示例值：** 修改仓库根目录 `.env`，不要改 `deploy/env.example`。
- **修改 `.env` 后旧密码仍有效：** 密码只会在执行 `bootstrap-dev.ps1` 时同步；修改后需要重跑脚本，成功后旧会话会被注销。
- **提示运行目录不是官方仓库：** 检查 `AUTOFLOW_RUNTIME` 指向的位置；脚本不会自动删除或覆盖已有目录。
- **提示容器未运行：** 确认 Docker 已启动，再重新执行 `.\scripts\bootstrap-dev.ps1`。
- **提示找不到 WSL 发行版：** 执行 `wsl --list --verbose`，把实际的 WSL2 Ubuntu 名称写入 `.env` 的 `AUTOFLOW_WSL_DISTRO`。
- **Windows Git 无法访问 GitHub：** WSL Docker 后端会自动改用 WSL Git，不需要修改全局 Git 配置。
- **8000 端口没有页面：** 初始化只创建容器和站点；还需要在单独终端执行 `.\scripts\bench.ps1 start`。
- **更换站点名：** 名称必须以 `.localhost` 结尾，并同步修改示例命令中的站点名。

当前脚本依据官方 `frappe_docker` 的 [`devcontainer-example/docker-compose.yml`](https://github.com/frappe/frappe_docker/blob/main/devcontainer-example/docker-compose.yml)、[`development/installer.py`](https://github.com/frappe/frappe_docker/blob/main/development/installer.py) 和[开发说明](https://github.com/frappe/frappe_docker/blob/main/docs/05-development/01-development.md)编写。2026-07-30 的首次成功安装已经把四个上游仓库的实际 40 位提交哈希回填到 `docs/research/upstream-baseline.md`。
