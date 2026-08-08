# 备份与恢复演练

## 验收目标

备份“成功生成”不等于能够恢复。AutoFlow 360 的验收要求同时完成：数据库备份、公有附件、私有附件、SHA-256 完整性校验、独立临时站点恢复、迁移、应用清单和最小数据读取。

Frappe 官方说明 `bench backup --with-files --compress` 会生成数据库及压缩附件备份；恢复时数据库文件是必需输入，公有和私有附件分别传给 `--with-public-files`、`--with-private-files`。参见 [bench backup](https://docs.frappe.io/framework/user/en/bench/reference/backup) 和 [bench restore](https://docs.frappe.io/framework/user/en/bench/reference/restore)。

## 本地开发环境演练

先确保开发容器正在运行，然后在 Windows 仓库根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-backup.ps1
```

包装脚本会在现有开发容器中运行 `scripts/verify-backup.sh`。它使用随机临时站点名，验证完毕后只删除脚本创建的站点和 `/tmp/autoflow-local-*` 临时目录。成功标志为：

```text
RESTORE_CHECK_PASSED
```

如果数据库被其他测试占用，会出现锁等待错误；先结束正在运行的集成测试，确认没有残留 Bench 测试进程，再重试。恢复失败时不要删除原站点或原备份。

## 生产 Compose 备份

```bash
chmod 600 deploy/oracle/compose.env
./deploy/oracle/backup.sh
```

备份保存到被 Git 忽略的 `deploy/oracle/backups/<UTC时间>/`。脚本使用容器内独立临时目录，复制出数据库、公有附件和私有附件后生成 `SHA256SUMS`，并立即重新校验。

生产恢复演练：

```bash
./deploy/oracle/restore-check.sh
```

也可以指定某个备份集，但路径必须位于本项目的备份根目录：

```bash
./deploy/oracle/restore-check.sh deploy/oracle/backups/20260801T120000Z
```

恢复脚本拒绝仓库外路径，且只删除名称带 `restore-check-` 的本次临时站点。它不会覆盖 `SITE_NAME` 指向的生产站点，也不使用强制删除参数。

## 安全和保留策略

- 备份包含业务数据、私有附件和站点配置，应按敏感数据处理；目录权限保持 600/700。
- `SHA256SUMS` 只能发现意外损坏，不能防止攻击者同时篡改文件和清单。异地副本应加密，并把清单或签名存到独立位置。
- 至少保留“每日 7 份、每周 4 份、每月 3 份”，但要根据免费磁盘容量调整；不得因为保留策略耗尽系统盘。
- 至少每月执行一次恢复演练，并在镜像升级、数据库迁移和重要功能发布前再执行一次。
- 当前脚本没有把备份自动上传第三方云存储，避免在未授权情况下外传数据。异地备份需要另行确认存储位置、费用、加密密钥和删除策略。
