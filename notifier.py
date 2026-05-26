import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)


class Notifier:
    """推送通知类 - 企业微信群机器人 + 邮件"""

    def __init__(self, wechat_webhook: str = None, mail_config: Dict = None):
        self.wechat_webhook = wechat_webhook
        self.mail_config = mail_config or {}

    def send_wechat_message(self, message: str):
        """发送企业微信群消息"""
        if not self.wechat_webhook:
            logger.warning("未配置企业微信webhook")
            return False

        try:
            data = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }

            response = requests.post(
                self.wechat_webhook,
                json=data,
                timeout=10
            )

            result = response.json()
            if result.get('errcode') == 0:
                logger.info("企业微信消息发送成功")
                return True
            else:
                logger.error(f"企业微信消息发送失败: {result}")
                return False

        except Exception as e:
            logger.error(f"发送企业微信消息异常: {e}")
            return False

    def send_email(self, subject: str, content: str):
        """发送邮件"""
        if not self.mail_config:
            logger.warning("未配置邮件参数")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.mail_config['from']
            msg['To'] = self.mail_config['to']
            msg['Subject'] = subject

            msg.attach(MIMEText(content, 'plain', 'utf-8'))

            with smtplib.SMTP(
                self.mail_config['server'],
                self.mail_config['port']
            ) as server:
                server.starttls()
                server.login(
                    self.mail_config['user'],
                    self.mail_config['password']
                )
                server.send_message(msg)

            logger.info("邮件发送成功")
            return True

        except Exception as e:
            logger.error(f"发送邮件异常: {e}")
            return False

    def send_arbitrage_alert(self, fund_list: List[Dict], alert_type: str = 'premium'):
        """发送套利告警

        Args:
            fund_list: 基金列表
            alert_type: premium(溢价) 或 discount(折价)
        """
        if not fund_list:
            return

        # 构建消息
        type_name = "溢价" if alert_type == 'premium' else "折价"

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = f"【LOF套利雷达 - {type_name}告警】\n\n"
        message += f"时间: {now}\n"
        message += f"发现 {len(fund_list)} 只高套利机会:\n\n"

        for i, fund in enumerate(fund_list, 1):
            message += f"{i}. {fund['code']} {fund['name']}\n"
            message += f"   类型: {fund['type']}\n"
            message += f"   场内价: {fund['market_price']:.3f} | iNAV: {fund['inav']:.3f}\n"
            message += f"   {type_name}率: {fund['premium_rate' if alert_type == 'premium' else 'discount_rate']:.2f}%\n"
            message += f"   扣费净收益: {fund['net_return']:.2f}%\n"
            message += f"   申购状态: {fund['purchase_status']}\n"
            message += f"   操作建议: {fund.get('suggestion', '')}\n\n"

        message += "---\nLOF套利雷达自动推送"

        # 发送企业微信
        self.send_wechat_message(message)

        # 发送邮件
        subject = f"LOF套利告警 - {type_name}"
        self.send_email(subject, message)

    def send_test_message(self):
        """发送测试消息"""
        message = f"LOF套利雷达测试消息\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n系统运行正常！"
        self.send_wechat_message(message)
        self.send_email("LOF套利雷达测试", message)


if __name__ == '__main__':
    # 测试
    wechat_webhook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"

    mail_config = {
        'server': 'smtp.qq.com',
        'port': 587,
        'user': 'your_email@qq.com',
        'password': 'your_auth_code',
        'from': 'your_email@qq.com',
        'to': 'your_email@qq.com'
    }

    notifier = Notifier(wechat_webhook, mail_config)
    notifier.send_test_message()
