# Cloudflare Quick Tunnel 临时演示

## 用途和限制

Quick Tunnel 把本机 `http://autoflow.localhost:8000` 临时映射为公网 HTTPS 地址，适合面试时短时间展示，不是生产托管。Cloudflare 官方把它定位为测试/开发能力：没有服务等级保证，当前还有限制并发请求数量且不支持服务器推送事件。限制以 [Quick Tunnel 官方文档](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) 为准。

公开隧道意味着任何知道地址的人都能访问登录页。只允许使用合成演示数据，管理员密码不得复用其他账号密码，演示结束立即按 `Ctrl+C` 关闭隧道。

## 安装

Windows 可使用官方发布包或 Windows 包管理器：

```powershell
winget install --id Cloudflare.cloudflared --exact
cloudflared --version
```

如果包管理器不可用，按 [cloudflared 官方安装说明](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) 下载与系统匹配的程序，不使用第三方镜像站。

## 启动

1. 先启动本地 Frappe 服务，并确认浏览器能打开 `http://autoflow.localhost:8000`。
2. 在仓库根目录运行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-tunnel.ps1
   ```

3. 脚本会先访问 `/api/method/ping`；健康检查通过后才启动隧道。
4. 从终端复制 `https://随机子域.trycloudflare.com`，用无痕窗口验证登录页和演示流程。
5. 演示结束按 `Ctrl+C`，再确认该地址已经不可访问。

脚本只允许本机 HTTP 地址，拒绝把任意远程服务转发出去。需要更换本地端口时可显式传入：

```powershell
.\scripts\start-tunnel.ps1 -OriginUrl "http://localhost:8000"
```

## 长期公网入口

需要稳定域名、访问策略和持续在线时，应使用命名 Tunnel、自有域名和 Cloudflare Access，或使用 `docs/deployment/oracle-always-free.md` 的单机 HTTPS 部署。它们涉及账号、DNS 和外部资源配置，不属于 Quick Tunnel 的零配置验收范围。
