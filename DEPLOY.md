# Deployment Guide | 部署指南

[中文](#中文) | [English](#english)

---

<a id="english"></a>

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
| `SECRET_KEY` | Flask session secret (**required**, generate via `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `INTERNAL_TOKEN` | Scheduler → `/api/refresh` auth token (**required**, otherwise auto-refresh gets 403) |
| `WECHAT_WEBHOOK` | WeChat Work bot webhook URL (optional) |
| `SMTP_HOST` / `SMTP_PORT` | SMTP server config (default smtp.qq.com:587) |
| `SMTP_USER` / `SMTP_PASSWORD` | Email notification credentials (auth code, not password) |
| `EMAIL_TO` | Alert email recipient (defaults to SMTP_USER) |
| `ARBITRAGE_THRESHOLD_ALERT` | Alert push threshold, net return % (default 3.0) |
| `A_SHARE_HOLIDAYS` | Comma-separated holiday dates to override built-in calendar (update yearly) |

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

---

<a id="中文"></a>

## 环境要求

- Linux 服务器（推荐 Ubuntu 20.04+）
- Python 3.8+
- 公网访问（用于获取东方财富市场数据）

## 第一步：服务器准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装依赖
sudo apt install -y python3 python3-pip git sqlite3 supervisor nginx
```

## 第二步：克隆项目并配置

```bash
git clone https://github.com/bobycade/LOF-Arbitrage-Radar.git
cd LOF-Arbitrage-Radar
pip3 install -r requirements.txt
cp .env.example .env
nano .env  # 编辑配置文件
```

## 第三步：一键部署

```bash
chmod +x quickstart.sh
bash quickstart.sh
```

该脚本会自动完成：
- 安装 Python 依赖
- 配置 Supervisor 进程管理
- 设置 Nginx 反向代理
- 配置定时自动刷新任务

## 第四步：Nginx 配置

创建 `/etc/nginx/sites-available/lof_arbitrage`：

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

## 第五步：Supervisor 配置

创建 `/etc/supervisor/conf.d/lof_arbitrage.conf`：

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

## 环境变量说明

`.env` 文件中的关键配置项：

| 变量 | 说明 |
|------|------|
| `SECRET_KEY` | Flask 会话密钥（**必须配置**，生成：`python -c "import secrets; print(secrets.token_hex(32))"`） |
| `INTERNAL_TOKEN` | 调度器调用 /api/refresh 的认证令牌（**必须配置**，否则定时刷新返回 403） |
| `WECHAT_WEBHOOK` | 企业微信群机器人 Webhook 地址（可选） |
| `SMTP_HOST` / `SMTP_PORT` | SMTP 服务器配置（默认 smtp.qq.com:587） |
| `SMTP_USER` / `SMTP_PASSWORD` | 邮件通知的账号和授权码（非登录密码） |
| `EMAIL_TO` | 告警收件邮箱（默认同 SMTP_USER） |
| `ARBITRAGE_THRESHOLD_ALERT` | 告警推送阈值：扣费后净收益 %（默认 3.0） |
| `A_SHARE_HOLIDAYS` | 法定节假日（逗号分隔），覆盖内置日历，需每年更新 |

## 验证部署

```bash
# 检查进程状态
sudo supervisorctl status

# 检查 Nginx
curl -I http://localhost

# 检查 Flask 应用
curl -s http://localhost:5000 | head -20
```

## 日常维护

```bash
# 重启应用
sudo supervisorctl restart lof_arbitrage_app

# 查看日志
tail -f /var/log/lof_arbitrage_app.log

# 备份数据库
cp lof_data.db lof_data_$(date +%Y%m%d).bak.db
```

---

项目详情请参考 [README.md](README.md)。
