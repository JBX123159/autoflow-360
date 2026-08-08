# Oracle Cloud 免费层部署

## 适用范围

这条路径用于把 AutoFlow 360 部署到单台 ARM64 云主机，保持 Docker Compose、MariaDB、Redis、Frappe/ERPNext/CRM 和 AutoFlow 360 的完整闭环。脚本复用官方 `frappe_docker` Compose 文件，并把上游固定到 `deploy/upstream-lock.json` 中的提交，不修改上游核心文件。

Oracle 的免费层政策、区域库存和账号资格可能变化，项目不承诺实例一定可申请或永久免费。创建资源前必须在 Oracle 控制台确认资源旁仍显示“始终免费”或等价标识；没有容量时不要切换到付费规格。以 [Oracle Cloud Free Tier 官方说明](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm) 为准。

## 前置条件

- 一台 64 位 ARM Linux 主机，或把 `AUTOFLOW_PLATFORM` 明确改成 `linux/amd64` 的兼容主机。
- Docker Engine 23 及以上、Docker Compose v2、Git、Python 3。
- 一个指向该主机公网 IP 的域名；防火墙仅开放 SSH、HTTP 80 和 HTTPS 443。
- 已发布的 `ghcr.io/jbx123159/autoflow-360:<标签>` 多架构镜像。仓库尚未发布前，镜像工作流不会成功，这是预期状态。
- 生产环境只放合成演示数据；真实客户、供应商、价格和联系人数据不属于当前免费演示范围。

官方镜像构建方式和 BuildKit 密钥用法见 [frappe_docker 自定义镜像文档](https://github.com/frappe/frappe_docker/blob/main/docs/02-setup/02-build-setup.md)。

## 首次部署

1. 克隆项目并切到已验收的发布标签。
2. 复制配置模板：

   ```bash
   cp deploy/oracle/compose.env.example deploy/oracle/compose.env
   chmod 600 deploy/oracle/compose.env
   ```

3. 用独立随机值替换所有 `CHANGE_ME`。可分别生成数据库和管理员密码：

   ```bash
   python3 -c 'import secrets; print(secrets.token_urlsafe(36))'
   ```

4. 确认以下值彼此匹配：

   ```dotenv
   SITE_NAME=demo.example.com
   FRAPPE_SITE_NAME_HEADER=demo.example.com
   SITES_RULE=Host(`demo.example.com`)
   ```

5. 运行部署：

   ```bash
   chmod +x deploy/oracle/*.sh
   ./deploy/oracle/deploy.sh
   ```

脚本会校验配置文件权限和占位符，检出锁定的官方 `frappe_docker` 提交，生成权限为 600 的本地 Compose 文件，拉取镜像并启动服务。目标站点不存在时才会自动创建站点并安装 ERPNext、CRM 和 AutoFlow 360；已有站点只执行迁移和应用清单检查。

## 验证与运维

```bash
docker compose --env-file deploy/oracle/compose.env \
  -f deploy/oracle/compose.generated.yaml ps
./deploy/oracle/backup.sh
./deploy/oracle/restore-check.sh
```

浏览器访问 `https://SITE_NAME`，确认 HTTPS、登录、角色工作台和三条合成演示场景。不要把 `compose.env`、生成的 Compose、备份、站点配置或日志上传到 GitHub。

## 更新与回滚边界

- 更新前先运行备份与恢复演练，保存镜像标签和 Git 发布标签。
- 只把 `CUSTOM_TAG` 改成已通过 CI 的不可变发布标签，再运行 `deploy.sh`。
- Frappe 不支持直接降级站点。需要回滚时，应恢复与旧镜像版本匹配的备份，而不是把新数据库直接交给旧镜像。
- 单机免费部署没有高可用；主机、磁盘或区域故障会造成停机。面试演示前应重新检查健康状态。

## 成本边界

项目脚本本身、GitHub 公共仓库、公开容器包和 Cloudflare Quick Tunnel 可以零软件许可费用使用。域名、超出免费额度的流量/磁盘、Oracle 付费资源和备份存储可能产生人民币费用，开通前必须在控制台核价并设置预算告警。
