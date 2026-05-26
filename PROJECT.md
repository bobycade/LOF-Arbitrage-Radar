# LOF-Arbitrage-Radar - Project Overview

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
├── README.md                   # Project documentation
├── DEPLOY.md                   # Deployment guide
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
- [DEPLOY.md](DEPLOY.md) - Deployment guide
- [LICENSE](LICENSE) - MIT License
