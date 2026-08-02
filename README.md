# LOF-Arbitrage-Radar

[中文](#中文) | [English](#english)

---

<a id="english"></a>

## LOF-Arbitrage-Radar

A real-time web application for monitoring LOF (Listed Open-end Fund) premium/discount arbitrage opportunities, with auto data refresh, historical trend analysis, and multi-channel alert notifications.

## Features

- **Real-time Monitoring** - Scan all LOF funds (Equity / Mixed / Commodity / QDII)
- **Premium Arbitrage** - Auto-calculate net yield after fees, highlight high-premium opportunities
- **Discount Arbitrage** - Monitor discount opportunities with actionable suggestions
- **QDII Zone** - Dedicated section for QDII-type LOFs with high-premium focus
- **NAV Trend Charts** - Historical NAV trend charts with 1M/3M/6M/1Y/All periods (Chart.js)
- **Smart Alerts** - Auto-push via WeChat Work bot + Email when net premium >= 3%
- **User System** - Registration, login, role-based access (admin/VIP/user)
- **Admin Panel** - User management, system config, audit logs
- **Fund Detail** - Full NAV history charts (since inception), performance, manager, announcement links
- **Favorites** - Personal watchlist with one-click detail access
- **Responsive Design** - PC and mobile friendly
- **Auto Refresh** - 5-min interval during trading hours + evening NAV catch-up (20:00-22:00)

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3 + Flask |
| Frontend | Vanilla JS + Chart.js |
| Database | SQLite |
| Process | Supervisor |
| Reverse Proxy | Nginx |

## Quick Start

### Prerequisites

- Python 3.8+
- pip

### Installation

```bash
git clone https://github.com/bobycade/LOF-Arbitrage-Radar.git
cd LOF-Arbitrage-Radar
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your config
python app.py
```

Open `http://localhost:5000` in your browser.

### Production Deploy

```bash
chmod +x quickstart.sh
bash quickstart.sh
```

See [DEPLOY.md](DEPLOY.md) for full deployment guide.

## Project Structure

```
LOF-Arbitrage-Radar/
├── app.py                      # Flask main application
├── data_fetcher.py             # Market data fetching (EastMoney API)
├── arbitrage_calculator.py     # Arbitrage profit calculation
├── database.py                 # SQLite database management
├── auth.py                     # User authentication & authorization
├── notifier.py                 # WeChat Work + Email notifications
├── scheduler.py                # Cron-like data refresh scheduler
├── requirements.txt            # Python dependencies
├── .env.example                # Environment config template
├── quickstart.sh               # One-click deploy script
├── LICENSE                     # MIT License
├── README.md                   # This file
├── DEPLOY.md                   # Detailed deployment guide
├── templates/
│   ├── index.html              # Main page
│   ├── login.html              # Login page
│   ├── register.html           # Registration page
│   └── admin/                  # Admin panel templates
└── static/
    ├── css/
    │   ├── style.css           # Main stylesheet
    │   └── admin.css           # Admin panel styles
    └── js/
        ├── app.js              # Frontend logic
        └── admin.js            # Admin panel logic
```

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_HOST` | `0.0.0.0` | Server bind address |
| `FLASK_PORT` | `5000` | Server port |
| `SECRET_KEY` | - | Flask session secret (**required in production**, random hex) |
| `INTERNAL_TOKEN` | - | Token for scheduler → `/api/refresh` auth (**required for auto refresh**) |
| `WECHAT_WEBHOOK` | - | WeChat Work bot webhook URL (optional) |
| `SMTP_HOST` | `smtp.qq.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | - | SMTP username |
| `SMTP_PASSWORD` | - | SMTP auth code (not password!) |
| `EMAIL_TO` | `SMTP_USER` | Alert email recipient |
| `ARBITRAGE_THRESHOLD_ALERT` | `3.0` | Alert threshold, net return % |
| `REFRESH_INTERVAL` | `5` | Data refresh interval (min, trading hours) |
| `A_SHARE_HOLIDAYS` | built-in 2026 | Comma-separated holiday dates, override calendar |

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Arbitrage Strategy

### Premium Arbitrage
- **Trigger**: Net premium >= 3%
- **Flow**: Subscribe (off-market) -> Transfer -> Sell (on-market)
- **Risk**: NAV may drop during T+2 settlement period

### Discount Arbitrage
- **Trigger**: Net discount >= 3%
- **Flow**: Buy (on-market) -> Transfer -> Redeem (off-market)
- **Risk**: Redemption fee may be high if held < 7 days

## Data Source

All market data is fetched from [EastMoney](https://fund.eastmoney.com/) public APIs:
- Fund list: `fund.eastmoney.com/js/fundcode_search.js`
- Real-time quotes: `push2.eastmoney.com/api/qt/ulist.np/get`
- iNAV estimates: `fundgz.1234567.com.cn/js/{code}.js`
- NAV history: `api.fund.eastmoney.com/f10/lsjz`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational and informational purposes only. It does not constitute investment advice. Use at your own risk.

---

<a id="中文"></a>

## LOF套利雷达

实时监控 LOF 基金溢价/折价套利机会的 Web 应用，支持自动数据刷新、历史趋势分析、多渠道告警推送。

## 功能特性

- **实时监控** - 全市场 LOF 基金扫描（股票型/混合型/商品型/QDII型）
- **溢价套利** - 自动计算扣费后净收益，推荐高溢价套利机会
- **折价套利** - 监控折价机会，提供折价套利建议
- **QDII专区** - 独立展示 QDII 型 LOF，重点关注高溢价品种
- **净值走势图** - 支持 1月/3月/6月/1年/全部 周期切换（Chart.js）
- **智能告警** - 净溢价 >= 3% 时自动推送企业微信 + 邮件通知
- **用户系统** - 注册、登录、角色权限控制（管理员/VIP/普通用户）
- **管理后台** - 用户管理、系统配置、操作审计日志
- **基金详情** - 成立以来全量净值走势、近期业绩、基金经理、公告直达链接
- **我的自选** - 个人自选跟踪，点击名称直达详情
- **响应式设计** - 支持PC和手机访问
- **自动刷新** - 交易时间每5分钟 + 晚间20-22点净值追更

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3 + Flask |
| 前端 | 原生 JS + Chart.js |
| 数据库 | SQLite |
| 进程管理 | Supervisor |
| 反向代理 | Nginx |

## 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装

```bash
git clone https://github.com/bobycade/LOF-Arbitrage-Radar.git
cd LOF-Arbitrage-Radar
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入实际配置
python app.py
```

浏览器打开 `http://localhost:5000` 即可访问。

### 生产部署

```bash
chmod +x quickstart.sh
bash quickstart.sh
```

完整部署指南请参考 [DEPLOY.md](DEPLOY.md)。

## 配置说明

复制 `.env.example` 为 `.env` 并按需配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FLASK_HOST` | `0.0.0.0` | 服务绑定地址 |
| `FLASK_PORT` | `5000` | 服务端口 |
| `SECRET_KEY` | - | Flask 会话密钥（**生产必填**，随机字符串，否则重启踢下线） |
| `INTERNAL_TOKEN` | - | scheduler 调用 /api/refresh 的令牌（**不配置则定时刷新失效**） |
| `WECHAT_WEBHOOK` | - | 企业微信群机器人 Webhook 地址（可选） |
| `SMTP_HOST` | `smtp.qq.com` | SMTP 服务器 |
| `SMTP_PORT` | `587` | SMTP 端口 |
| `SMTP_USER` | - | SMTP 用户名 |
| `SMTP_PASSWORD` | - | SMTP 授权码（不是邮箱密码！） |
| `EMAIL_TO` | `SMTP_USER` | 告警收件邮箱 |
| `ARBITRAGE_THRESHOLD_ALERT` | `3.0` | 告警阈值：扣费后净收益（%） |
| `REFRESH_INTERVAL` | `5` | 交易时段数据刷新间隔（分钟） |
| `A_SHARE_HOLIDAYS` | 内置2026 | 法定节假日（逗号分隔），可覆盖内置日历 |

版本更新历史见 [CHANGELOG.md](CHANGELOG.md)。

## 套利策略

### 溢价套利
- **触发条件**：净溢价 >= 3%
- **操作流程**：场外申购 → 转托管到场内 → 场内卖出
- **风险提示**：T+2 交收期内净值可能下跌，溢价可能消失
- **特别注意**：暂停申购的基金无法操作

### 折价套利
- **触发条件**：净折价 >= 3%
- **操作流程**：场内买入 → 转托管到场外 → 场外赎回
- **风险提示**：赎回价不确定，持有 <7 天赎回费较高
- **特别注意**：赎回到账需 3-4 个交易日

## 数据来源

所有行情数据来自 [东方财富](https://fund.eastmoney.com/) 公开 API：
- 基金列表：`fund.eastmoney.com/js/fundcode_search.js`
- 实时行情：`push2.eastmoney.com/api/qt/ulist.np/get`
- 实时估值：`fundgz.1234567.com.cn/js/{code}.js`
- 历史净值：`api.fund.eastmoney.com/f10/lsjz`

## 参与贡献

欢迎提交 Pull Request 参与贡献！

## 许可证

本项目基于 MIT 许可证开源，详见 [LICENSE](LICENSE) 文件。

## 免责声明

本工具仅供学习和参考使用，不构成任何投资建议。使用风险自负。
