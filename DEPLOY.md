# Deployment Guide

## Requirements

- A Linux server (Ubuntu 20.04+ recommended)
- Python 3.8+
- Public network access (to fetch market data from EastMoney APIs)

## Step 1: Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip git sqlite3 supervisor nginx
```

## Step 2: Clone & Configure

```bash
git clone https://github.com/bobycade/LOF-Arbitrage-Radar.git
cd LOF-Arbitrage-Radar
pip3 install -r requirements.txt
cp .env.example .env
nano .env  # Edit with your config
```

## Step 3: One-click Deploy

```bash
chmod +x quickstart.sh
bash quickstart.sh
```

This script will:
- Install Python dependencies
- Configure Supervisor for process management
- Set up Nginx reverse proxy
- Configure auto-refresh cron job

## Step 4: Nginx Configuration

Create `/etc/nginx/sites-available/lof_arbitrage`:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 120s;
    }

    location /static/ {
        alias /path/to/LOF-Arbitrage-Radar/static/;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/lof_arbitrage /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

## Step 5: Supervisor Configuration

Create `/etc/supervisor/conf.d/lof_arbitrage.conf`:

```ini
[program:lof_arbitrage_app]
command=/usr/bin/python3 /path/to/LOF-Arbitrage-Radar/app.py
directory=/path/to/LOF-Arbitrage-Radar
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/lof_arbitrage_app.log
environment=PYTHONUNBUFFERED="1"

[program:lof_arbitrage_scheduler]
command=/usr/bin/python3 /path/to/LOF-Arbitrage-Radar/scheduler.py
directory=/path/to/LOF-Arbitrage-Radar
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/lof_arbitrage_scheduler.log
environment=PYTHONUNBUFFERED="1"
```

```bash
sudo supervisorctl reread && sudo supervisorctl update
sudo supervisorctl start lof_arbitrage_app lof_arbitrage_scheduler
```

## Environment Variables

Key variables in `.env`:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Flask session secret (generate a random string!) |
| `WECHAT_WEBHOOK` | WeChat Work bot webhook URL |
| `SMTP_USER` / `SMTP_PASSWORD` | Email notification credentials |
| `ALERT_THRESHOLD` | Alert push threshold (%) |

## Verify Deployment

```bash
# Check process status
sudo supervisorctl status

# Check Nginx
curl -I http://localhost

# Check Flask directly
curl -s http://localhost:5000 | head -20
```

## Maintenance

```bash
# Restart application
sudo supervisorctl restart lof_arbitrage_app

# View logs
tail -f /var/log/lof_arbitrage_app.log

# Backup database
cp lof_data.db lof_data_$(date +%Y%m%d).bak.db
```

---

For project details, see [README.md](README.md).
