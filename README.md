# 活动报名与签到管理系统

单机构、多活动的报名与签到管理平台。当前已完成 **v0.2 报名闭环**：管理后台的活动与报名管理、微信小程序的报名/我的报名/电子票、后台审核与名额控制。扫码核销、签到统计与数据导出进入 v0.3。

完整产品与技术规划见 [活动报名签到系统-规划.md](活动报名签到系统-规划.md)，下一阶段执行计划见 [下一阶段-报名闭环开发规划.md](下一阶段-报名闭环开发规划.md)，项目交接说明见 [项目交接文档.md](项目交接文档.md)。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 管理后台 | Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router |
| 后端 API | Python 3.12+ / FastAPI / SQLAlchemy 2.0（异步）/ Alembic |
| 数据库 | 本地默认 SQLite；Docker / 生产使用 MySQL 8.4 |
| 鉴权 | JWT + Argon2 密码哈希 |
| 部署 | Docker Compose + Nginx |

## 目录结构

```
.
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/admin/       # 后台接口（认证、活动、报名管理）
│   │   ├── api/mp/          # 小程序接口（登录、活动、报名、电子票）
│   │   ├── core/            # 配置、安全、异常、限流、电子票签名
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic 模型
│   │   ├── services/        # 业务逻辑（报名、审核、表单校验）
│   │   └── main.py
│   ├── alembic/             # 数据库迁移
│   ├── scripts/             # 初始化脚本
│   └── tests/               # 接口测试
├── admin-web/               # Vue 3 管理后台
│   └── src/
│       ├── api/             # 请求封装
│       ├── views/           # 登录、活动列表/编辑、报名管理
│       ├── layouts/
│       ├── router/
│       └── stores/
├── miniprogram/             # 微信小程序（原生）
│   ├── pages/               # 活动列表、详情、报名、我的报名、电子票、个人中心
│   ├── utils/               # 请求、登录、日期
│   ├── config.js            # API 地址与 Mock 登录配置
│   └── project.config.json
├── docker-compose.yml
└── 活动报名签到系统-规划.md
```

## 本地启动

环境要求：Python 3.12+、Node.js 20+。本项目已在 Python 3.13、Node.js 24 下验证。

### 1. 启动后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
cp .env.example .env
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/create_admin.py --username admin --password admin12345 --name 系统管理员
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

> 后端 `.env.example` 默认 `WECHAT_MOCK_LOGIN=true`，用于小程序开发期 Mock 登录。生产环境必须关闭。
>
> macOS / Linux 请将 `.venv/Scripts/python.exe` 换成 `.venv/bin/python`。

后端启动后：

- API 地址：http://127.0.0.1:8000
- 接口文档：http://127.0.0.1:8000/docs
- 默认使用 `backend/event_system.db`（SQLite），无需安装数据库

### 2. 启动管理后台

```bash
cd admin-web
npm install
npm run dev
```

打开 http://localhost:5173 ，使用本地初始化的账号登录：

- 账号：`admin`
- 密码：`admin12345`

> 该密码仅用于本地开发，部署前务必重新创建强密码账号，并删除或禁用示例账号。

### 3. 启动微信小程序

1. 保持后端运行，并确认 `backend/.env` 中 `WECHAT_MOCK_LOGIN=true`。
2. 使用微信开发者工具导入 `miniprogram/` 目录，AppID 可选择测试号。
3. 在开发者工具「详情 → 本地设置」中勾选“不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书”。
4. 默认请求 `http://127.0.0.1:8000`，配置位于 `miniprogram/config.js`。

说明：

- 开发期使用 `mock:<MOCK_USER>` 登录，修改 `MOCK_USER` 可以模拟不同用户。
- 真机调试时，将 `API_BASE` 改为电脑的局域网 IP，并确保手机与电脑在同一网络。
- 上线前必须改为已备案的 HTTPS 域名，关闭 Mock 登录，并配置真实 AppID / AppSecret。
- 小程序代码已完成语法与配置校验，但尚未在微信开发者工具中实际运行（当前环境未安装）。

## 运行测试

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q
```

当前覆盖：登录、限流、角色越权、活动管理、乐观锁、表单/时间锁定、Mock 微信登录、报名（免审核/需审核）、重复报名、名额边界、取消与复用、表单校验、审核与批量审核、报名统计、电子票与二维码、生产环境密钥校验，共 48 个用例。

## 当前已实现

- 管理员账号密码登录、JWT 鉴权、角色校验
- 登录失败限流：同一 IP + 账号连续失败 5 次后锁定 15 分钟，成功登录后重置
- 活动创建、编辑、列表、关键词/状态筛选、分页
- 活动发布、下架、结束状态流转；仅草稿可删除
- 活动编辑乐观锁：使用 `version` 防止多管理员互相覆盖
- 已有报名后锁定报名表单结构与报名时间；名额不能低于已报名人数
- 生产环境启动时强制校验 `JWT_SECRET` 与 `TICKET_SECRET`，拒绝弱密钥
- 报名表单动态配置：系统字段（姓名、手机号）+ 自定义字段（文本、多行、手机号、邮箱、数字、单选、多选、日期）
- 后端按表单 Schema 校验必填字段、字段类型、选项合法性、系统字段存在性
- 微信小程序 Mock 登录与真实 `code2session` 登录
- 小程序活动列表/详情、报名、我的报名、取消报名、电子票二维码
- 名额原子扣减与释放，重复报名拦截，取消/拒绝后复用报名记录
- 电子票 HMAC 签名 + PNG 二维码接口
- 后台报名名单：状态/关键词筛选、分页、详情、单条/批量审核、管理员取消、基础统计
- 关键操作写入 `audit_log`
- 统一响应体与异常处理：`{ code, message, data }`
- 响应式管理后台界面
- 前端活动时间先后校验、未保存离开提示、报名字段上移/下移
- Element Plus 按需引入，前端主包由约 869 KB 降至约 140 KB
- Docker 部署：后端非 root 运行、服务健康检查、后端不直接暴露端口、Nginx 真实 IP 透传
- GitHub Actions CI：后端迁移与测试、前端类型检查与构建
- MySQL 备份脚本：`scripts/backup-mysql.cmd`

## 尚未实现（v0.3）

- 扫码核销、签到记录、手动检索核销
- 报名/签到统计趋势、Excel 导出
- 站内通知与微信订阅消息
- 封面上传（当前填写图片 URL）
- 管理员账号管理界面、修改密码界面
- 多场次、候补、支付

建议按规划文档中的里程碑顺序推进：先完成报名闭环，再做签到核销。

## Docker 部署

本机已安装 **Docker Engine 27.3.1 + Docker Compose v2.31.0**，运行在 WSL2 的 Alpine 发行版 `DockerAlpine` 中。由于 Docker Desktop 官方下载域名在当前网络下被重置，因此没有使用 Docker Desktop，而是安装了功能等价的 Docker Engine。

Windows 侧没有全局 `docker` 命令，请使用项目提供的包装器 `scripts/docker.cmd`。它会自动启动 Docker 守护进程，并在当前目录执行命令：

```bash
.\scripts\docker.cmd version
.\scripts\docker.cmd compose version
```

> Git Bash 中使用 `./scripts/docker.cmd`。也可以直接执行 `wsl -d DockerAlpine -- docker ...`。

部署步骤：

```bash
cp .env.example .env
# 修改 .env 中的 MYSQL_ROOT_PASSWORD、MYSQL_PASSWORD、JWT_SECRET、TICKET_SECRET
# JWT_SECRET / TICKET_SECRET 至少 32 位，可用 openssl rand -hex 32 生成
# 小程序生产环境还需配置 WECHAT_APPID / WECHAT_SECRET

.\scripts\docker.cmd compose up -d --build
.\scripts\docker.cmd compose exec backend python scripts/create_admin.py --username admin --password 你的强密码 --name 系统管理员
```

> 后端以 `ENVIRONMENT=production` 运行，如果 `JWT_SECRET` / `TICKET_SECRET` 为空、使用默认值或少于 32 位，会拒绝启动；生产环境强制关闭 Mock 登录；MySQL 密码也请务必修改。

访问 http://localhost:8080 。

- Docker 守护进程按需启动，首次执行命令可能需要几秒钟
- 后端容器以非 root 用户 `app` 运行，且不向宿主机暴露 8000 端口，只通过 Nginx 访问
- MySQL、后端、管理后台均配置健康检查，管理后台在后端健康后启动
- Uvicorn 信任 Nginx 代理头，审计日志与登录限流使用真实客户端 IP
- MySQL 数据保存在 `mysql_data` 数据卷；`docker compose down` 不会删除数据卷
- 构建默认使用清华 PyPI 与 npmmirror，可通过 `PIP_INDEX_URL`、`NPM_REGISTRY` 环境变量覆盖
- 管理后台由 Nginx 提供，`/api` 反向代理到后端
- 已配置 `docker.m.daocloud.io` 作为镜像加速；如失效，修改 WSL 内的 `/etc/docker/daemon.json`
- 生产环境必须修改 `JWT_SECRET` 与数据库密码
- 数据备份：执行 `.\scripts\backup-mysql.cmd`，SQL 文件写入 `scripts/backups/`
- 停止服务：`.\scripts\docker.cmd compose down`（保留数据卷）
- 如需 Docker Desktop 图形界面，需要自备离线安装包或可访问官方 CDN 的网络环境

Docker 安装脚本位于 `scripts/install-docker-engine.ps1`，安装包缓存位于 `scripts/downloads/`（已加入 `.gitignore`，确认不再需要重装后可删除以释放约 350 MB 空间）。

## 关键约定

### 时间格式

当前按本地时间（Asia/Shanghai）存储，前后端统一使用 `YYYY-MM-DDTHH:mm:ss`，不携带时区。若后续需要跨时区支持，再统一切换为 UTC。

### API 响应

成功：

```json
{ "code": 0, "message": "ok", "data": {} }
```

失败时 HTTP 状态码与业务 `code` 对应，例如 `401 / 40103` 表示用户名或密码错误。

### 报名表单 Schema

```json
[
  { "key": "name", "label": "姓名", "type": "text", "required": true, "system": true },
  { "key": "phone", "label": "手机号", "type": "phone", "required": true, "system": true },
  { "key": "company", "label": "所在单位", "type": "text", "required": false }
]
```

## 下一阶段建议

1. 实现扫码核销与签到记录（v0.3）。
2. 增加报名/签到统计、趋势与 Excel 导出。
3. 接入站内通知与微信订阅消息。
4. 补充管理员账号管理、封面上传与按活动授权。
5. 提前办理小程序账号、域名备案与 HTTPS，避免阻塞提审。
