#!/usr/bin/env python3
"""
LOF套利雷达 - 定时数据刷新脚本
此脚本用于自动定时刷新数据并发送告警
"""

import requests
import time
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# 加载配置
load_dotenv('config.env')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def refresh_data():
    """刷新数据"""
    try:
        logger.info("开始定时刷新数据...")

        server_url = f"http://{os.getenv('SERVER_HOST', 'localhost')}:{os.getenv('SERVER_PORT', '5000')}"

        response = requests.post(
            f"{server_url}/api/refresh",
            timeout=120  # 2分钟超时
        )

        result = response.json()

        if result.get('success'):
            logger.info(f"定时刷新成功！更新了 {result.get('count', 0)} 只基金")
            return True
        else:
            logger.error(f"定时刷新失败: {result.get('error')}")
            return False

    except Exception as e:
        logger.error(f"定时刷新异常: {e}")
        return False


def main():
    """主函数 - 循环执行定时任务"""
    logger.info("LOF套利雷达定时任务启动")

    # 刷新间隔（分钟）
    refresh_interval = int(os.getenv('REFRESH_INTERVAL', '5'))

    while True:
        try:
            # 检查是否在交易时间
            now = datetime.now()
            hour = now.hour
            minute = now.minute
            weekday = now.weekday()  # 0=周一, 6=周日

            # 周末不刷新
            if weekday >= 5:  # 周六(5)和周日(6)
                logger.info("周末，跳过刷新")
                time.sleep(refresh_interval * 60)
                continue

            # 只在交易时间刷新（9:30-15:00）
            if 9 <= hour < 15:
                refresh_data()
            else:
                logger.info("非交易时间，跳过刷新")

        except Exception as e:
            logger.error(f"定时任务执行异常: {e}")

        # 等待下一次刷新
        logger.info(f"等待 {refresh_interval} 分钟后进行下一次刷新...")
        time.sleep(refresh_interval * 60)


if __name__ == '__main__':
    main()
