#!/usr/bin/env python3
"""
LOF套利雷达 - 定时数据刷新脚本 v6.0
此脚本用于自动定时刷新数据并发送告警
[v6.0] 刷新时段重构:
  - 交易时段 9:25-15:05: 按 REFRESH_INTERVAL 正常刷新（覆盖集合竞价结束后到收盘）
  - 晚间 20:00-22:00: 每 30 分钟刷新一次（净值陆续公布，收盘后核对当日净值）
  - 其余时段（含周末/法定节假日）: 跳过
[v6.0] 调用 /api/refresh 携带 X-Internal-Token 内部令牌
"""

import requests
import time
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# 加载配置（.env 优先，config.env 兼容旧配置）
load_dotenv('.env')
load_dotenv('config.env')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ A股法定节假日（休市日）============
# 按国务院公告每年更新；可用环境变量 A_SHARE_HOLIDAYS 覆盖（逗号分隔 YYYY-MM-DD）
_DEFAULT_HOLIDAYS_2026 = [
    '2026-01-01', '2026-01-02',                                  # 元旦
    '2026-02-16', '2026-02-17', '2026-02-18', '2026-02-19', '2026-02-20',  # 春节
    '2026-04-06',                                                # 清明节
    '2026-05-01', '2026-05-04', '2026-05-05',                    # 劳动节
    '2026-06-19',                                                # 端午节
    '2026-09-25',                                                # 中秋节
    '2026-10-01', '2026-10-02', '2026-10-05', '2026-10-06',
    '2026-10-07', '2026-10-08',                                  # 国庆节
]


def _load_holidays():
    """从环境变量 A_SHARE_HOLIDAYS 读取节假日，未配置时用内置当年预测值"""
    env = os.getenv('A_SHARE_HOLIDAYS', '')
    if env.strip():
        return {d.strip() for d in env.split(',') if d.strip()}
    return set(_DEFAULT_HOLIDAYS_2026)


HOLIDAYS = _load_holidays()

# 晚间净值公布时段固定刷新间隔（分钟）
EVENING_INTERVAL = 30


def is_market_closed(now):
    """判断指定时刻是否休市（周末或法定节假日）"""
    return now.weekday() >= 5 or now.strftime('%Y-%m-%d') in HOLIDAYS


def should_refresh(now):
    """判断当前时刻是否应该刷新数据

    Args:
        now: datetime 当前时刻

    Returns:
        (should_refresh: bool, reason: str) — reason 用于日志与测试
    """
    if is_market_closed(now):
        return False, '休市（周末/法定节假日）'
    hm = (now.hour, now.minute)
    if (9, 25) <= hm <= (15, 5):
        return True, '交易时段'
    if (20, 0) <= hm <= (22, 0):
        return True, '晚间净值时段'
    return False, '非刷新时段'


def refresh_data():
    """刷新数据"""
    try:
        logger.info("开始定时刷新数据...")

        server_url = f"http://{os.getenv('SERVER_HOST', 'localhost')}:{os.getenv('SERVER_PORT', '5000')}"

        response = requests.post(
            f"{server_url}/api/refresh",
            headers={'X-Internal-Token': os.getenv('INTERNAL_TOKEN', '')},
            timeout=120  # 2分钟超时
        )

        result = response.json()

        if result.get('success'):
            logger.info(f"定时刷新任务已受理: {result.get('message', '刷新任务已启动')}")
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
        # 默认等待时长：交易时段按配置，非刷新时段也按配置轮询检查
        wait_minutes = refresh_interval
        try:
            now = datetime.now()
            ok, reason = should_refresh(now)
            if ok:
                logger.info(f"触发刷新（{reason}）")
                refresh_data()
                if reason == '晚间净值时段':
                    wait_minutes = EVENING_INTERVAL
            else:
                logger.info(f"{reason}，跳过刷新")

        except Exception as e:
            logger.error(f"定时任务执行异常: {e}")

        # 等待下一次刷新
        logger.info(f"等待 {wait_minutes} 分钟后进行下一次刷新...")
        time.sleep(wait_minutes * 60)


if __name__ == '__main__':
    main()
