# 活动报名与签到管理系统

单机构、多活动的报名与签到管理平台。当前为 **v0.1 骨架版**，已完成管理后台的登录与活动管理闭环，小程序端、报名、审核和扫码核销将在下一阶段接入。

完整产品与技术规划见 [活动报名签到系统-规划.md](活动报名签到系统-规划.md)，下一阶段执行计划见 [下一阶段-报名闭环开发规划.md](下一阶段-报名闭环开发规划.md)。

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
│   │   ├── api/admin/       # 后台接口（认证、活动）
│   │   ├── core/            # 配置、安全、异常处理
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic 模型
│   │   ├── services/        # 业务逻辑
│   │   └── main.py
│   ├── alembic/             # 数据库迁移
│   ├── scripts/             # 初始化脚本
│   └── tests/               # 接口测试
├── admin-web/               # Vue 3 管理后台
│   └── src/
│       ├── api/             # 请求封装
│       ├── views/           # 登录、活动列表、活动编辑
│       ├── layouts/
│       ├── router/
│       └── stores/
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
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/create_admin.py --username admin --password admin12345 --name 系统管理员
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

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

## 运行测试

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q
```

当前覆盖：登录成功/失败、未登录拦截、登录失败限流与成功重置、活动创建与列表、关键词筛选、编辑、发布状态流转、删除限制、时间与表单校验、乐观锁、名额下限、已有报名后的表单/报名时间锁定、生产环境密钥校验，共 22 个用例。

## 当前已实现

- 管理员账号密码登录、JWT 鉴权、角色校验
- 登录失败限流：同一 IP + 账号连续失败 5 次后锁定 15 分钟，成功登录后重置
- 活动创建、编辑、列表、关键词/状态筛选、分页
- 活动发布、下架、结束状态流转；仅草稿可删除
- 活动编辑乐观锁：使用 `version` 防止多管理员互相覆盖
- 已有报名后锁定报名表单结构与报名时间；名额不能低于已报名人数
- 生产环境启动时强制校验 `JWT_SECRET`，拒绝默认值或少于 32 位的密钥
- 报名表单动态配置：系统字段（姓名、手机号）+ 自定义字段（文本、多行、手机号、邮箱、数字、单选、多选、日期）
- 后端按表单 Schema 校验必填字段、字段标识唯一性、系统字段存在性
- 关键操作写入 `audit_log`
- 统一响应体与异常处理：`{ code, message, data }`
- 响应式管理后台界面
- GitHub Actions CI：后端迁移与测试、前端类型检查与构建

## 尚未实现（下一阶段）

- 微信小程序登录、活动浏览、报名、电子票
- 报名名单、审核、名额并发控制、取消报名
- 扫码核销、手动检索兜底、签到记录
- 数据统计、Excel 导出、站内通知
- 封面图片上传（当前填写图片 URL）
- 管理员账号管理界面、修改密码界面

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
# 修改 .env 中的 MYSQL_ROOT_PASSWORD、MYSQL_PASSWORD、JWT_SECRET
# JWT_SECRET 至少 32 位，可用 openssl rand -hex 32 生成

.\scripts\docker.cmd compose up -d --build
.\scripts\docker.cmd compose exec backend python scripts/create_admin.py --username admin --password 你的强密码 --name 系统管理员
```

> 后端以 `ENVIRONMENT=production` 运行，如果 `JWT_SECRET` 为空、使用默认值或少于 32 位，会拒绝启动；MySQL 密码也请务必修改。

访问 http://localhost:8080 。

- Docker 守护进程按需启动，首次执行命令可能需要几秒钟
- MySQL 数据保存在 `mysql_data` 数据卷
- 管理后台由 Nginx 提供，`/api` 反向代理到后端
- 已配置 `docker.m.daocloud.io` 作为镜像加速；如失效，修改 WSL 内的 `/etc/docker/daemon.json`
- 生产环境必须修改 `JWT_SECRET` 与数据库密码
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

1. 新增 `attendee`、`registration`、`checkin` 模型与迁移。
2. 实现小程序登录（`code2session`）与活动列表/详情接口。
3. 实现报名提交与名额原子扣减（`taken_count` 条件更新）。
4. 实现后台名单、审核、导出，再做扫码核销。
5. 提前办理小程序账号、域名备案与 HTTPS，避免阻塞提审。
