# 知遇运营后台 API（本地开发）

此目录是运营后台的 FastAPI 服务。它直接读取 `premeet-backend/sessions.sqlite3` 中的真实本地账户、档案、会员权益、房间和安全状态；不另建一套用户库。

## 启动

最简单的方式：双击项目根目录的 `启动运营后台.cmd`。它会分别打开 API 与后台网页两个命令窗口；使用期间请不要关闭它们。脚本已拆分为纯 ASCII 的启动器，避免 Windows `cmd` 因中文编码或嵌套括号错误解析启动命令。

首次安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

启动：

```powershell
.\start.ps1
```

若提示端口 `8200` 被占用，请不要重复启动：先访问 `http://127.0.0.1:8200/health`。能看到 `"status":"ok"` 即表示 API 已正常运行；新版 `start.ps1` 会自动识别这一情况。

接口文档：`http://127.0.0.1:8200/docs`

## 本地管理员登录

首次启动会创建一个仅用于本机测试的超级管理员：

```text
用户名：admin
密码：LocalAdmin!2026
```

启动前可复制 `.env.example` 为 `.env`，设置 `ADMIN_BOOTSTRAP_USERNAME` 和 `ADMIN_BOOTSTRAP_PASSWORD` 覆盖首次管理员。管理员登录后由浏览器保存 8 小时的本地会话；登录、登出、冻结账号和调整会员权益都会写入应用级追加审计日志。

本地接口文档：`http://127.0.0.1:8200/docs`。

> 这是本地开发方案，不可直接暴露到公网。生产环境还需替换默认密码、使用 HTTPS、接入企业身份认证，并把审计日志放入受访问控制的生产数据库。
