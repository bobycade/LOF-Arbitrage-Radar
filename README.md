# LOF-Arbitrage-Radar (LOF套利雷达)

实时监控 LOF 基金溢价/折价套利机会的 Web 应用，支持自动数据刷新、历史趋势分析、多渠道告警推送。

## Features

- **Real-time Monitoring** - Scan all LOF funds (Equity / Mixed / Commodity / QDII)
- **Premium Arbitrage** - Auto-calculate net yield after fees, highlight high-premium opportunities
- **Discount Arbitrage** - Monitor discount opportunities with actionable suggestions
- **QDII Zone** - Dedicated section for QDII-type LOFs with high-premium focus
- **NAV Trend Charts** - Historical NAV trend charts with 1M/3M/6M/1Y/All periods (Chart.js)
- **Smart Alerts** - Auto-push via WeChat Work bot + Email when net premium >= 3%
- **User System** - Registration, login, role-based access (admin/VIP/user)
- **Admin Panel** - User management, system config, audit logs
- **Responsive Design** - PC and mobile friendly
- **Auto Refresh** - 5-minute interval during trading hours

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
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `5000` | Server port |
| `WECHAT_WEBHOOK` | - | WeChat Work bot webhook URL |
| `SMTP_SERVER` | `smtp.qq.com` | SMTP server |
| `SMTP_USER` | - | SMTP username |
| `SMTP_PASSWORD` | - | SMTP auth code (not password!) |
| `ALERT_THRESHOLD` | `3.0` | Alert threshold (%) |
| `SHOW_THRESHOLD` | `1.5` | Display threshold (%) |
| `REFRESH_INTERVAL` | `5` | Data refresh interval (min) |

## Arbitrage Strategy

### Premium Arbitrage (溢价套利)
- **Trigger**: Net premium >= 3%
- **Flow**: Subscribe (off-market) -> Transfer -> Sell (on-market)
- **Risk**: NAV may drop during T+2 settlement period

### Discount Arbitrage (折价套利)
- **Trigger**: Net discount >= 3%
- **Flow**: Buy (on-market) -> Transfer -> Redeem (off-market)
- **Risk**: Redemption fee may be high if held < 7 days

## Data Source

All market data is fetched from [EastMoney (东方财富)](https://fund.eastmoney.com/) public APIs:
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
