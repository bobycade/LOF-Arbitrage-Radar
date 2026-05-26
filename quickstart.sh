#!/bin/bash
# LOF套利雷达 - 一键部署脚本（Ubuntu/Debian）
# 使用方法：bash quickstart.sh

set -e

echo "=========================================="
echo "  LOF套利雷达 - 一键部署脚本"
echo "=========================================="
echo ""

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用root用户运行此脚本"
    exit 1
fi

# 更新系统
echo "📦 更新系统..."
apt update && apt upgrade -y

# 安装基础软件
echo "📦 安装基础软件..."
apt install python3 python3-pip git sqlite3 supervisor nginx -y

# 检查是否存在项目目录
if [ ! -d "/root/lof_arbitrage" ]; then
    echo "❌ 项目目录不存在！"
    echo "请先上传项目文件到 /root/lof_arbitrage"
    exit 1
fi

# 进入项目目录
cd /root/lof_arbitrage

# 安装Python依赖
echo "📦 安装Python依赖..."
pip3 install -r requirements.txt

# 配置环境变量
if [ ! -f ".env" ]; then
    echo "📝 配置环境变量..."
    cp .env.example .env
    echo "⚠️  请手动编辑 .env 文件，填入你的配置"
    echo "   nano .env"
fi

# 初始化数据库
echo "🗄️  初始化数据库..."
python3 -c "from database import DatabaseManager; DatabaseManager().init_database()"

# 配置supervisor
echo "⚙️  配置supervisor..."
cat > /etc/supervisor/conf.d/lof_arbitrage.conf <<EOF
[program:lof_arbitrage]
command=/usr/bin/python3 /root/lof_arbitrage/app.py
directory=/root/lof_arbitrage
user=root
autostart=true
autorestart=true
startsecs=5
startretries=3
redirect_stderr=true
stdout_logfile=/var/log/lof_arbitrage.log
environment=PYTHONUNBUFFERED="1"
EOF

# 重新加载supervisor配置
supervisorctl reread
supervisorctl update

# 启动应用
echo "🚀 启动应用..."
supervisorctl start lof_arbitrage

# 配置定时任务
echo "⏰ 配置定时任务..."
(crontab -l 2>/dev/null | grep -v "lof_arbitrage"; echo "*/5 * * * * cd /root/lof_arbitrage && /usr/bin/python3 scheduler.py >> /var/log/lof_scheduler.log 2>&1") | crontab -

# 配置防火墙（如果使用UFW）
if command -v ufw &> /dev/null; then
    echo "🔥 配置防火墙..."
    ufw allow 5000/tcp
fi

echo ""
echo "=========================================="
echo "  ✅ 部署完成！"
echo "=========================================="
echo ""
echo "📝 后续步骤："
echo "1. 编辑配置文件: nano /root/lof_arbitrage/.env"
echo "2. 填入企业微信webhook和邮件配置"
echo "3. 重启应用: supervisorctl restart lof_arbitrage"
echo "4. 访问网页: http://YOUR_IP:5000"
echo ""
echo "📊 常用命令："
echo "  查看日志: tail -f /var/log/lof_arbitrage.log"
echo "  重启应用: supervisorctl restart lof_arbitrage"
echo "  查看状态: supervisorctl status"
echo ""
