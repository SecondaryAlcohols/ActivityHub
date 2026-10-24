# ActivityHub 后端

校园活动报名与考勤系统后端，按 `prototype-android` 原型的用户端 / 管理端交互实现。
技术栈：**FastAPI + SQLAlchemy 2.0（异步）+ PostgreSQL + Alembic**。

原型里的五类考勤方式（动态二维码、静态口令、GPS、IP、人脸）在本后端中都是**真实校验**，
而不是界面演示：签名验证、时间窗、服务端距离计算、网段判定、人脸相似度阈值、单次使用防重放、
同 IP 多账号预警、名额并发控制、审计留痕均已落地。

---

## 1. 功能范围

### 用户端

| 模块 | 能力 |
| --- | --- |
| 活动 | 列表（按临近时间 / 历史筛选、关键字搜索）、详情（名额、报名截止、考勤方式、主办方） |
| 报名 | 报名、取消、重新报名；需审核的活动进入待审核；名额满 / 已截止 / 重复报名有明确错误码 |
| 电子票 | HMAC-SHA256 签名票据，可离线验签，含持票人、活动、有效期 |
| 考勤中心 | 按活动配置返回所需校验项、签到/签退时间窗、口令有效期倒计时、当前是否可考勤及阻断原因 |
| 签到 / 签退 | 一次性提交全部凭证，服务端逐项校验；返回核验方式、距离、人脸相似度、异常提示 |
| 我的 | 个人资料、我的报名、我的考勤记录（待签退 / 已完成）、人脸录入与状态 |

### 管理端

| 模块 | 能力 |
| --- | --- |
| 活动管理 | 创建（草稿）、编辑、发布、取消；考勤模式（仅签到 / 签到+签退）与五种方式任意叠加 |
| 考勤配置 | 二维码刷新周期、静态口令与有效期、GPS 半径与精度上限、IP 网段、人脸阈值 |
| 签到控制台 | 二维码 + 同步 6 位口令（默认 10 秒刷新）、报名/签到/签退/签到率/异常统计、最近考勤流 |
| 实时流 | SSE 推送控制台快照，仅在数据变化时下发，15 秒心跳保活 |
| 名单 | 全部 / 已签到 / 已签退 / 未签到 / 异常 / 待审核筛选，按姓名、学号、手机号、IP 搜索 |
| 补签 | 人工补签写入审计日志并生成待复核异常，不允许覆盖已有记录 |
| 异常 | 同 IP 多账号、连续校验失败、人工补签；可处理 / 忽略并留痕 |
| 统计导出 | 近 N 天签到率概览；考勤明细 CSV（UTF-8 BOM，Excel 直接打开） |
| 审计 | 活动变更、审核、补签、导出、异常处理等敏感操作全量记录 |

---

## 2. 目录结构

```
app/
├── main.py                 # 应用工厂、生命周期、健康探针、中间件
├── api/
│   ├── deps.py             # 认证 / 角色 / 分页依赖
│   ├── errors.py           # 统一错误响应
│   └── v1/                 # auth / events / registrations / admin_events / admin_console
├── core/                   # 配置、JWT、Argon2、HMAC、限流、日志、请求上下文
├── db/                     # 声明式基类、异步会话
├── models/                 # 12 张业务表 + 枚举
├── schemas/                # 请求 / 响应契约（Pydantic v2）
├── services/
│   ├── checkin/            # 五种校验器 + 流水线
│   ├── attendance.py       # 考勤上下文、提交、异常检测、补签
│   ├── admin_events.py     # 活动管理、二维码签发
│   ├── console.py          # 控制台、名单、异常、统计、导出
│   └── ...                 # auth / registrations / events / profile / audit / face
├── providers/face.py       # 人脸比对 Provider（stub / http）
└── utils/                  # Haversine、CIDR、UTC 时间
alembic/                    # 迁移（初始版本含全部表、枚举、约束、索引）
scripts/seed.py             # 演示数据
tests/                      # 34 个接口级测试
```

分层约定：**API 只做参数与鉴权 → service 承担业务与事务 → model 只描述持久化**。
服务层显式 `commit`，异常路径由会话依赖统一回滚。

---

## 3. 快速开始

### 3.1 本地运行

要求：Python ≥ 3.11、PostgreSQL ≥ 14（本地验证使用 18.6）。

```bash
# 1) 创建数据库与账号
psql -U postgres -c "CREATE ROLE activityhub LOGIN PASSWORD 'activityhub';"
psql -U postgres -c "CREATE DATABASE activityhub OWNER activityhub;"
psql -U postgres -c "CREATE DATABASE activityhub_test OWNER activityhub;"

# 2) 安装依赖
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[dev]"

# 3) 配置环境变量
copy .env.example .env             # 修改 DATABASE_URL / SECRET_KEY

# 4) 建表 + 演示数据
alembic upgrade head
python -m scripts.seed

# 5) 启动
uvicorn app.main:app --reload
```

打开 <http://127.0.0.1:8000/docs> 查看交互式文档。

### 3.2 Docker Compose

```bash
docker compose up -d --build
docker compose exec api python -m scripts.seed
```

### 3.3 演示账号

| 角色 | 账号 | 密码 | 说明 |
| --- | --- | --- | --- |
| 管理员 | `A0001` | `Passw0rd!` | 可查看全部活动与审计日志 |
| 组织者 | `T1001` | `Passw0rd!` | 计算机协会，拥有进行中的分享会 |
| 组织者 | `T1002` | `Passw0rd!` | 校青协，静态口令活动（口令 `826519`） |
| 学生 | `2023010118` | `Passw0rd!` | 陈雨桐，分享会已签到 |

> 演示数据中的分享会已签到 5 人，其中 2 人因同一 IP 被标记异常；活动时间相对当前时间生成，
> 重新执行 `python -m scripts.seed --reset` 可刷新到“正在进行中”的状态。

---

## 4. 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `production` 时启用配置护栏（弱密钥、stub 人脸、通配 CORS 直接拒绝启动） |
| `DATABASE_URL` | 本地 `activityhub` | 必须是 `postgresql+asyncpg://` |
| `SECRET_KEY` | 开发占位值 | JWT / 票据 / 二维码签名密钥，生产必须替换 |
| `ACCESS_TOKEN_TTL_MINUTES` | `60` | 访问令牌有效期 |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | 刷新令牌有效期（轮换 + 撤销） |
| `FACE_PROVIDER` | `stub` | `stub` 仅开发；`http` 对接外部人脸服务 |
| `FACE_ENCRYPTION_KEY` | 由 SECRET_KEY 派生 | 人脸特征加密密钥（Fernet） |
| `TRUST_PROXY_HEADERS` | `false` | 仅当部署在可信反向代理后开启，否则 `X-Forwarded-For` 可伪造 |
| `CORS_ORIGINS` | `*` | 逗号分隔；生产禁止 `*` |
| `CAMPUS_CIDRS` | 内网三段 | IP 考勤未配置白名单时的兜底网段 |

完整列表见 `.env.example`。

---

## 5. 关键设计

### 5.1 考勤校验流水线

`services/checkin/` 下每种方式独立实现，`run()` 按配置顺序执行，任一失败即中断：

```
二维码 → 静态口令 → GPS → IP → 人脸
```

先校验“在场证明”，再校验位置与网络，最后做开销最大的人脸比对。通过的方式会写入
`attendance_records.verified_methods`，作为事后复核证据。

| 方式 | 服务端校验 |
| --- | --- |
| 动态二维码 | `nonce.signature` HMAC 校验 + 有效期 + 活动归属 + `qr_usages` 唯一约束保证同一用户单次使用 |
| 静态口令 | Argon2 哈希比对 + 显式有效期（缺省为整个考勤窗口）；明文只在创建/轮换响应中出现一次 |
| GPS | Haversine 距离 ≤ 半径；定位精度超过阈值直接拒绝，避免“粗定位蒙混” |
| IP | 客户端 IP 命中 CIDR 白名单；默认只信任 TCP 对端，反代场景需显式开启 |
| 人脸 | 特征模板比对，低于阈值拒绝；模板加密存储，原图不落库 |

失败会写入 `checkin_attempts`，窗口内失败次数达到上限（默认 5 次 / 10 分钟）触发限流与异常记录。

### 5.2 名额与并发

报名在事务内 `SELECT ... FOR UPDATE` 锁定活动行，再统计 `pending + approved` 占位数量，
从数据库层避免并发超卖；`(event_id, user_id)` 唯一约束兜底重复报名。取消后重新报名复用原记录与电子票号。

### 5.3 动态二维码

控制台轮询 `GET /admin/events/{id}/qr`：有效则复用，过期自动签发新 challenge（TTL = 刷新周期 + 2 秒）。
每 10 秒落库一条，签发记录可审计；二维码内容包含活动、nonce、过期时间的 HMAC 签名，
即使泄露也无法跨活动使用。大屏同时展示的 6 位口令由 nonce 派生，可手动输入作为扫码兜底。

### 5.4 异常判定

- **同 IP 多账号**：同一活动、同一 IP、15 分钟窗口内出现 ≥ 2 个用户 → 双方记录标记 `flagged`，各生成一条待处理异常（不阻断，校园 NAT 场景常见）。
- **连续校验失败**：达到失败上限时生成异常，便于排查代签/撞库。
- **人工补签**：补签记录标记 `flagged` 并生成 `manual_override` 异常，同时写审计日志。

### 5.5 实时控制台

SSE（`text/event-stream`）每 2 秒取一次快照，仅在“统计 / 最近记录 / 异常 / 二维码”指纹变化时推送，
否则每 15 秒发心跳；流内使用独立数据库会话，避免长连接持有请求级会话。

### 5.6 安全与隐私

- 密码与静态口令使用 Argon2id；登录失败不区分账号不存在与密码错误，并执行等耗时校验。
- JWT 访问令牌 + 可撤销刷新令牌（轮换时旧 token 立即失效，行锁防并发重放）。
- 登录限流（IP + 账号，10 次 / 5 分钟），考勤失败限流（5 次 / 10 分钟）。
- 统一错误结构 `{"error": {"code", "message", "details"}}`，不泄漏堆栈；500 只记录服务端日志。
- 生产环境配置护栏；安全响应头；请求 ID 贯穿访问日志。
- 人脸仅保存加密特征，`/auth/face` 支持录入与状态查询，原始图像不写磁盘。

---

## 6. API 概览

基础路径 `/api/v1`，完整字段与示例见 `/docs`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/register` `/auth/login` `/auth/refresh` `/auth/logout` | 认证 |
| GET | `/auth/me` `/auth/face` | 当前用户、人脸状态 |
| PUT | `/auth/face` | 录入 / 更新人脸 |
| GET | `/events` `/events/{id}` | 活动列表 / 详情（可匿名） |
| GET | `/events/{id}/attendance` | 考勤上下文 |
| POST | `/events/{id}/attendance/checkin` `/checkout` | 签到 / 签退 |
| POST | `/events/{id}/registrations` | 报名 |
| DELETE | `/registrations/{id}` | 取消报名 |
| GET | `/me/registrations` `/me/registrations/{id}/ticket` `/me/attendance` | 我的报名 / 电子票 / 考勤 |
| GET POST PATCH | `/admin/events` `/admin/events/{id}` | 活动管理 |
| POST | `/admin/events/{id}/publish` `/cancel` | 发布 / 取消 |
| POST | `/admin/events/{id}/static-code/rotate` | 轮换口令（明文仅返回一次） |
| GET POST | `/admin/events/{id}/qr` `/qr/rotate` | 获取 / 强制刷新二维码 |
| GET | `/admin/events/{id}/console` `/console/stream` | 控制台快照 / SSE |
| GET | `/admin/events/{id}/roster` `/anomalies` | 名单 / 异常 |
| POST | `/admin/registrations/{id}/approve` `/reject` `/manual-checkin` | 审核 / 补签 |
| POST | `/admin/anomalies/{id}/resolve` | 处理异常 |
| GET | `/admin/events/{id}/export.csv` `/admin/stats/overview` | 导出 / 统计 |
| GET | `/admin/audit-logs` | 审计日志（管理员） |
| GET | `/health/live` `/health/ready` | 探针 |

### 常见错误码

| HTTP | code | 场景 |
| --- | --- | --- |
| 409 | `already_registered` / `event_full` / `registration_closed` | 报名冲突 |
| 409 | `already_checked_in` / `already_checked_out` | 重复考勤 |
| 422 | `qr_required` `qr_invalid` `qr_expired` `qr_already_used` | 二维码 |
| 422 | `static_code_required` `static_code_invalid` `static_code_window_closed` | 静态口令 |
| 422 | `gps_required` `gps_out_of_range` `gps_accuracy_low` | GPS |
| 422 | `ip_not_allowed` | IP 网段 |
| 422 | `face_required` `face_not_enrolled` `face_low_similarity` | 人脸 |
| 422 | `checkin_not_open` `checkin_closed` `checkout_before_checkin` `checkout_closed` | 时间窗 |
| 429 | `too_many_attempts` / `login_rate_limited` | 限流 |
| 403 | `forbidden` | 跨组织访问 |

---

## 7. 测试

```bash
# 需要 activityhub_test 数据库
pytest -q
ruff check app tests scripts
```

当前 34 个测试，覆盖：注册登录与令牌轮换、报名/取消/审核/名额、二维码重放与过期、
静态口令窗口、GPS 越界与精度、IP 白名单、人脸阈值、签到签退链路、名单筛选、
补签审计、同 IP 异常、导出与统计、跨组织越权。

---

## 8. 生产部署清单

1. `ENVIRONMENT=production`，配置 ≥ 32 位随机 `SECRET_KEY`，关闭 DEBUG。
2. `FACE_PROVIDER=http` 并配置 `FACE_PROVIDER_URL` / `FACE_PROVIDER_TOKEN`；`stub` 会被启动护栏拒绝。
3. 前置 Nginx / 网关终止 TLS，设置 `TRUST_PROXY_HEADERS=true` 且只接受来自该代理的流量。
4. `CORS_ORIGINS` 收敛为 App / 管理端域名，禁止 `*`。
5. 多实例部署时，把进程内限流替换为 Redis 实现（`SlidingWindowLimiter` 接口不变）。
6. 数据库开启备份与 PITR；`refresh_tokens`、`qr_challenges`、`checkin_attempts` 建议定期归档。
7. 前置代理需为 SSE 关闭缓冲（`X-Accel-Buffering: no` 已返回）。

---

## 9. 已知边界

- 人脸识别通过 Provider 抽象对接外部服务，仓库内 `stub` 仅用于开发与测试，不具备生物识别能力。
- 动态二维码的“截图转发”只能在时间片与单次使用层面限制；若需更强防护，可叠加设备指纹或人脸。
- 名单、导出按活动全量查询，单场规模（数千人）内表现良好；更大规模建议导出走异步任务。
- 未实现消息推送、候补队列、活动签到地点地图选点，这些是后续迭代方向。
