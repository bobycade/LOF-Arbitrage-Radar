# LOF-Arbitrage-Radar - Project Overview | 项目概览

[中文](#中文) | [English](#english)

---

<a id="english"></a>

## Summary

A complete LOF fund arbitrage monitoring and alert system.

## Features

### Core
- Full-market LOF fund scanning (Equity / Mixed / Commodity / QDII)
- Real-time on-market price collection (EastMoney API)
- Intraday iNAV estimation (TianTian Fund)
- Premium/discount arbitrage yield calculation (after fees)
- Subscription status real-time query (Normal / Limited / Suspended)
- Historical premium records (SQLite)

### Arbitrage Calculation
- Premium: `Net Return = Premium Rate - Subscription Fee - Sell Commission`
- Discount: `Net Return = Discount Rate - Buy Commission - Redemption Fee`
- Threshold: Show >= 1.5%, Highlight + Push >= 3%

### Web Interface
- Premium arbitrage rankings
- Discount arbitrage rankings
- QDII dedicated section
- Fund search
- Historical NAV trend charts (Chart.js)
- Responsive design (PC + Mobile)

### Alerts
- WeChat Work bot push
- Email notification (SMTP)
- Auto trigger when net premium/discount >= 3%
- Duplicate prevention

### Automation
- Scheduled data refresh (every 5 min, trading hours only)
- Auto-start via Supervisor
- Auto cleanup of old data

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
├── README.md                   # Project documentation (bilingual)
├── DEPLOY.md                   # Deployment guide (bilingual)
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

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3 + Flask |
| Frontend | Vanilla JS + Chart.js |
| Database | SQLite |
| Process Manager | Supervisor |
| Reverse Proxy | Nginx |

## Documentation

- [README.md](README.md) - Project documentation (bilingual)
- [DEPLOY.md](DEPLOY.md) - Deployment guide (bilingual)
- [LICENSE](LICENSE) - MIT License

---

<a id="中文"></a>

## 概述

完整的 LOF 基金套利监控与告警系统。

## 功能特性

### 核心功能
- 全市场 LOF 基金扫描（股票型 / 混合型 / 商品型 / QDII 型）
- 实时场内价格采集（东方财富 API）
- 日内 iNAV 实时估值（天天基金）
- 溢价/折价套利收益率计算（扣费后）
- 申购状态实时查询（正常 / 限额 / 暂停）
- 历史溢价数据记录（SQLite）

### 套利计算
- 溢价套利：`净收益 = 溢价率 - 申购费 - 卖出佣金`
- 折价套利：`净收益 = 折价率 - 买入佣金 - 赎回费`
- 阈值规则：显示 >= 1.5%，高亮 + 推送 >= 3%

### Web 界面
- 溢价套利排行
- 折价套利排行
- QDII 专区
- 基金搜索
- 历史净值走势图（Chart.js）
- 响应式设计（PC + 手机）

### 告警通知
- 企业微信群机器人推送
- 邮件通知（SMTP）
- 净溢价/折价 >= 3% 时自动触发
- 去重防扰

### 自动化
- 交易时段每 5 分钟定时刷新数据
- Supervisor 开机自启动
- 自动清理过期数据

## 项目结构

```
LOF-Arbitrage-Radar/
├── app.py                      # Flask 主应用
├── data_fetcher.py             # 市场数据采集（东方财富 API）
├── arbitrage_calculator.py     # 套利收益计算
├── database.py                 # SQLite 数据库管理
├── auth.py                     # 用户认证与授权
├── notifier.py                 # 企业微信 + 邮件通知
├── scheduler.py                # 定时数据刷新调度器
├── requirements.txt            # Python 依赖
├── .env.example                # 环境配置模板
├── quickstart.sh               # 一键部署脚本
├── LICENSE                     # MIT 许可证
├── README.md                   # 项目文档（中英双语）
├── DEPLOY.md                   # 部署指南（中英双语）
├── templates/
│   ├── index.html              # 主页面
│   ├── login.html              # 登录页面
│   ├── register.html           # 注册页面
│   └── admin/                  # 管理后台模板
└── static/
    ├── css/
    │   ├── style.css           # 主样式表
    │   └── admin.css           # 管理后台样式
    └── js/
        ├── app.js              # 前端逻辑
        └── admin.js            # 管理后台逻辑
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3 + Flask |
| 前端 | 原生 JS + Chart.js |
| 数据库 | SQLite |
| 进程管理 | Supervisor |
| 反向代理 | Nginx |

## 文档

- [README.md](README.md) — 项目文档（中英双语）
- [DEPLOY.md](DEPLOY.md) — 部署指南（中英双语）
- [LICENSE](LICENSE) — MIT 许可证
