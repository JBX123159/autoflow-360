# 管理员指南

## 初始化与角色

安装或迁移会幂等创建七类内部角色、客户/供应商门户角色和必要自定义字段。管理员负责把用户绑定到正确角色、Company User Permission、项目成员以及 Customer/Supplier Portal User；生产环境不应给普通业务人员 Administrator 或 System Manager。

## 演示数据

在本地站点执行：

```powershell
.\scripts\seed-demo.ps1
```

脚本只允许 Administrator 调用，使用固定 `demo_key` 幂等生成三条 CNY 合成场景和四个演示用户。用户密码不写入源码，管理员应单独设置一次性演示密码，演示后轮换。删除演示数据需要显式确认短语，先备份再执行。

## AI 设置

AI 默认关闭。启用时只有 AutoFlow Administrator/System Manager 可编辑 Base URL、模型和 Password 类型 API key。上线前确认数据能否发送到该服务；当前代码允许 HTTP(S)，正式环境应只允许批准的 HTTPS 域名。AI 输出只是建议，必须由人核对来源，不得把它当成已执行动作。

## 权限检查

每次新建公司、批量导入用户或角色变化后，用两个客户、两个供应商、两个公司做正反向验证：应看见自己的记录，同时无法通过列表、搜索、直接 URL 和 API 读取他方记录。参考 `autoflow_360/tests/test_permissions.py`。

## 运维

- 本地开发、Oracle、Quick Tunnel 和备份分别见 `docs/deployment/`。
- 每次升级前运行静态、集成、浏览器和恢复测试。
- 监测登录失败、PermissionError、锁超时、后台队列、磁盘、备份和最近成功恢复时间。
- `compose.env`、`.env`、站点配置、私有附件和备份不得提交 Git；真实数据进入系统前先落实加密、异地备份、限流和隐私制度。
