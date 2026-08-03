# Changelog / 更新日志

All notable changes to this project will be documented in this file.
本文件记录项目的所有重要变更。

---

## [v6.3] - 2026-08-03

### 中文
- **自选改为后端存储 + 本地兜底**：登录用户的自选存入后端 `user_favorites` 表（跨设备/清缓存不丢失），增删实时同步；游客仍用浏览器 `localStorage`，标签在有数据时可见
- 首次登录自动将本地存量自选迁移到后端账号（INSERT OR IGNORE 幂等，不丢已有数据）
- **修复 `GET /api/favorites` 后端崩溃（500）**：原代码用 `f['fund_code']` 取 `get_all_funds()` 返回的别名键（实为 `code`）导致 KeyError；并修正 `profit_after_fee` 取值列名、以及 `else` 分支直接塞 `sqlite3.Row` 引发的序列化问题
- 静态资源版本号 app.js `?v=6.3` 破缓存

### English
- **Favorites now backend-backed with localStorage fallback**: logged-in users' watchlist persists in `user_favorites` (survives cache clear / multiple devices), add/remove synced in real time; guests keep using `localStorage` with the tab shown when non-empty
- First login auto-migrates existing local favorites into the account (idempotent, no data loss)
- Bumped app.js asset version to `?v=6.3` to bust cache

## [v6.2] - 2026-08-02

### 中文

**P0 致命修复**
- 修复告警通知双重 Bug：`check_alerts` 字段不完整 + `mail_config` 缺 `from` 键，导致企微/邮件告警从未成功发出
- `premium_history` 增加 `(fund_code, nav_date)` 唯一索引（v6 迁移），修复 `INSERT OR REPLACE` 失效导致的数据库无限膨胀（实测 145MB → VACUUM 后 2MB）
- 折价套利赎回费 0.5% → **1.5%**：折价路径持有期 <7 天适用惩罚性费率，此前系统性高估收益约 1 个百分点
- 新增晚间 20:00-22:00 净值刷新窗口（每 30 分钟），修复收盘后/盘前溢价率错位

**P1 安全与性能**
- `/api/refresh` 增加 `X-Internal-Token` / admin 双认证（此前任何人可触发全量采集）
- `SECRET_KEY` 移除公开默认值，未配置时启动警告并使用临时随机密钥
- 数据采集改 10 线程并发：单轮 2-4 分钟 → 约 30 秒
- `DatabaseManager` 进程级单例（`get_db()`），消除每请求重复初始化
- 手动刷新改后台线程执行，不再阻塞 HTTP 请求
- 修复 session 生命周期全局污染（登录时不再修改全局配置）
- 榜单查询改用 `fund_code` 分组取最新（修复部分刷新失败时基金从榜单丢失）
- LOF 列表改按名称 `(LOF)` 标识筛选（覆盖 502 等此前缺失的代码前缀）

**P2 业务修正**
- QDII 申购 T+3 确认 / 赎回资金 T+7+ 到账提示；QDII 无实时估值的偏差提示
- 内置 2026 年法定节假日历（可用 `A_SHARE_HOLIDAYS` 覆盖，需每年更新）
- 当日无成交基金自动标记不可套利（防停牌虚假信号）
- 告警去重状态持久化（重启后不重复告警）
- 依赖瘦身：移除未使用的 pandas/plotly/schedule/bs4/lxml，新增 gunicorn

**前端**
- 基金详情：全量历史净值（pingzhongdata 代理 + 5 分钟缓存 + lsjz 回退），修复走势图时间段筛选无效、"共 N 条"与实际数据不符
- 申购状态旁新增「公告↗」链接（主表格 / 搜索卡片 / 详情弹窗），直达天天基金公告页
- 「我的自选」列表基金名称可点击打开详情
- 修复畸形分页参数（page=abc）导致接口 500

### English

**P0 Critical Fixes**
- Fixed dual alert-notification bugs (incomplete alert fields + missing `from` key in mail config) that prevented all WeChat/email alerts from ever being sent
- Added UNIQUE index on `(fund_code, nav_date)` in `premium_history` (v6 migration) — `INSERT OR REPLACE` was silently failing, causing unbounded DB growth (145MB → 2MB after VACUUM)
- Discount arbitrage redemption fee corrected 0.5% → 1.5% (punitive rate for <7-day holding); net returns were systematically overestimated by ~1%
- Added evening refresh window (20:00-22:00 every 30min) to capture same-day NAVs, fixing pre-market premium rate misalignment

**P1 Security & Performance**
- `/api/refresh` now requires `X-Internal-Token` header or admin session
- Removed public fallback for `SECRET_KEY`
- Concurrent data fetching (10 threads): 2-4 min → ~30s per refresh cycle
- Singleton `DatabaseManager` via `get_db()`
- Manual refresh runs in background thread (non-blocking HTTP)
- Fixed global session-lifetime pollution on login
- Leaderboard queries use `MAX(id) GROUP BY fund_code` (fixes funds disappearing on partial refresh)
- LOF list filtered by `(LOF)` name marker (covers 502-prefix funds)

**P2 Business Logic**
- QDII T+3 confirmation / T+7+ settlement hints; no-intraday-valuation notice
- Built-in 2026 A-share holiday calendar (override via `A_SHARE_HOLIDAYS`)
- Zero-turnover funds marked as non-arbitrageable
- Alert dedup state persisted across restarts
- Dependencies slimmed down; gunicorn added

**Frontend**
- Full NAV history in fund detail (pingzhongdata proxy + 5min cache + lsjz fallback)
- "Announcement↗" link next to purchase status (main tables / search cards / detail drawer)
- Favorites list fund names now clickable to open detail
- Fixed HTTP 500 on malformed pagination params

---

## [v5.1] - 2026-05-27

### 中文
- 基金详情弹窗：基本信息 / 近期业绩 / 基金经理（后端代理解决 CORS）
- 净值历史数据源切换：f10/lsjz → pingzhongdata/{code}.js（全量加载、默认"今年"周期、统计摘要、分页表格）
- 东方财富 API 频率控制：_safe_request()、随机抖动、/api/refresh 60s 冷却
- 榜单查询修复部分刷新丢基金问题

### English
- Fund detail drawer: basic info / performance / manager (backend proxy to solve CORS)
- NAV history data source migrated to pingzhongdata (full loading, YTD default, stats summary, paged table)
- EastMoney API rate limiting: _safe_request(), jitter, refresh cooldown
- Fixed funds missing from leaderboards on partial refresh

---

## [v5.0] - 2026-05-26

### 中文
- 管理后台：用户管理（封禁/角色/重置密码/软删除）、系统配置、操作审计日志
- 数据库版本化迁移机制

### English
- Admin panel: user management (ban/role/reset-password/soft-delete), system config, audit logs
- Versioned database migration mechanism

---

## [v4.0] - 2026-04-08

### 中文
- 用户认证系统：注册/登录/登出（用户名或邮箱 + 密码，werkzeug 哈希）
- 宽松访问模式：游客预览前 30 条，登录解锁全量数据/导出/历史/自选
- 我的自选（user_favorites 表）

### English
- User authentication: register/login/logout (username or email + password)
- Guest mode: preview first 30 rows; login unlocks full data/export/history/favorites
- Favorites (user_favorites table)
