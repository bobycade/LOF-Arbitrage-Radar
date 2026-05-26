"""
LOF套利雷达 - 套利计算模块 v2.0
修复:
1. 折价套利明确标注"赎回价未知"的风险
2. 净收益改名为更清晰的"扣除费用后预估收益"
3. 费率说明更详细
4. QDII基金额外风险提示
"""
import logging

logger = logging.getLogger(__name__)


class ArbitrageCalculator:
    """LOF套利计算类"""

    # 交易佣金费率（默认万五）
    TRADING_COMMISSION = 0.0005

    def __init__(self):
        pass

    def calculate_premium_arbitrage(self, fund_data):
        """
        计算溢价套利收益
        操作: 场内卖出 → 申购基金份额 → T+2/3确认 → 场内卖出
        风险: 确认期间净值可能下跌
        """
        try:
            premium_rate = fund_data['premium_rate']
            purchase_fee = fund_data.get('purchase_fee', 0.0012)
            purchase_status = fund_data.get('purchase_status', '正常')
            purchase_limit = fund_data.get('purchase_limit', 0)
            fund_type = fund_data.get('type', '')
            is_qdii = fund_type == 'QDII'

            # 暂停申购时仍然计算理论收益，标注风险提示
            is_suspended = purchase_status in ('暂停申购', '暂停')

            # 扣费净收益 = 溢价率 - 申购费率 - 卖出佣金
            net_return = premium_rate - (purchase_fee * 100) - (self.TRADING_COMMISSION * 100)
            waiting_days = 2  # 申购确认约T+2

            # 暂停申购时用默认费率（通常1.5%）估算
            if is_suspended:
                net_return = premium_rate - 1.5 - (self.TRADING_COMMISSION * 100)

            # 生成操作建议
            if is_suspended:
                suggestion = f'当前{purchase_status}，理论溢价{premium_rate:.2f}%，扣费后约{net_return:.2f}%'
                risk = '⚠️ 暂停申购无法操作，待开放申购后关注；开放后需评估确认期间净值下跌风险'
            elif net_return >= 3.0:
                suggestion = f'溢价{premium_rate:.2f}%，扣费后预估{net_return:.2f}%，T+{waiting_days}确认'
                risk = '注意确认期间净值下跌风险'
            elif net_return >= 1.5:
                suggestion = f'溢价{premium_rate:.2f}%，扣费后约{net_return:.2f}%，T+{waiting_days}确认'
                risk = '溢价有限，需评估确认期间风险'
            else:
                suggestion = f'溢价{premium_rate:.2f}%，扣费后{net_return:.2f}%，覆盖成本不足'
                risk = '空间不足'

            # 限额提示
            if purchase_status in ('限制大额', '限额'):
                if purchase_limit and purchase_limit > 0:
                    if purchase_limit >= 10000:
                        suggestion += f'，限额{purchase_limit / 10000:.0f}万/日'
                    else:
                        suggestion += f'，限额{purchase_limit}元/日'
                else:
                    suggestion += '，有限额'

            # QDII额外提示
            if is_qdii:
                risk += '；QDII基金净值受隔夜外盘影响大'

            return {
                'can_arbitrage': net_return >= 1.5,
                'net_return': round(net_return, 2),
                'waiting_days': waiting_days,
                'suggestion': suggestion,
                'risk': risk
            }

        except Exception as e:
            logger.error(f"计算溢价套利失败: {e}")
            return {
                'can_arbitrage': False,
                'net_return': 0,
                'waiting_days': 0,
                'suggestion': '计算错误',
                'risk': '数据异常'
            }

    def calculate_discount_arbitrage(self, fund_data):
        """
        计算折价套利收益
        操作: 场内买入 → 赎回基金份额 → T+1/2确认 → 按赎回日净值结算
        重要风险: 赎回价格是赎回日的未知净值，非当前净值！
        """
        try:
            discount_rate = fund_data['discount_rate']
            redemption_fee = fund_data.get('redemption_fee', 0.005)
            fund_type = fund_data.get('type', '')
            redemption_status = fund_data.get('redemption_status', '未知')
            is_qdii = fund_type == 'QDII'

            # 暂停赎回时仍然计算理论收益，标注风险提示
            is_redemption_suspended = redemption_status == '暂停赎回'

            # 理论扣费净收益 = 折价率 - 买入佣金 - 赎回费
            # 注意: 这是基于当前净值的预估，实际赎回价未知！
            net_return = discount_rate - (self.TRADING_COMMISSION * 100) - (redemption_fee * 100)
            waiting_days = 3  # 场内买入T+1份额到账，赎回T+1确认

            # 生成操作建议（强调风险）
            if is_redemption_suspended:
                suggestion = f'当前{redemption_status}，理论折价{discount_rate:.2f}%，扣费后约{net_return:.2f}%'
                risk = '⚠️ 暂停赎回无法操作；且赎回价未知，实际收益取决于赎回日净值'
            elif net_return >= 3.0:
                suggestion = f'折价{discount_rate:.2f}%，理论扣费后{net_return:.2f}%'
                risk = '赎回价未知，实际收益取决于赎回日净值'
            elif net_return >= 1.5:
                suggestion = f'折价{discount_rate:.2f}%，理论扣费后约{net_return:.2f}%'
                risk = '赎回价不确定，存在净值波动风险'
            else:
                suggestion = f'折价{discount_rate:.2f}%，扣费后{net_return:.2f}%，覆盖成本不足'
                risk = '空间不足'

            # QDII额外提示
            if is_qdii:
                risk += '；QDII基金隔夜外盘波动可能导致赎回价偏离'

            return {
                'can_arbitrage': net_return >= 1.5,
                'net_return': round(net_return, 2),
                'waiting_days': waiting_days,
                'suggestion': suggestion,
                'risk': risk
            }

        except Exception as e:
            logger.error(f"计算折价套利失败: {e}")
            return {
                'can_arbitrage': False,
                'net_return': 0,
                'waiting_days': 0,
                'suggestion': '计算错误',
                'risk': '数据异常'
            }

    def calculate_all(self, fund_data_list):
        """批量计算所有基金的套利数据"""
        results = []

        for fund in fund_data_list:
            premium_result = self.calculate_premium_arbitrage(fund)
            discount_result = self.calculate_discount_arbitrage(fund)

            fund['premium_arbitrage'] = premium_result
            fund['discount_arbitrage'] = discount_result

            results.append(fund)

        return results


if __name__ == '__main__':
    # 测试
    test_fund = {
        'code': '161725',
        'name': '招商中证白酒指数',
        'type': '股票',
        'market_price': 1.250,
        'nav': 1.200,
        'nav_date': '2026-04-02',
        'inav': 1.200,
        'is_inav': False,
        'premium_rate': 4.17,
        'discount_rate': -4.17,
        'purchase_status': '开放申购',
        'purchase_limit': 999999999,
        'purchase_fee': 0.0015,
        'redemption_fee': 0.005,
        'redemption_status': '开放赎回',
    }

    calc = ArbitrageCalculator()
    premium = calc.calculate_premium_arbitrage(test_fund)
    discount = calc.calculate_discount_arbitrage(test_fund)

    print("溢价套利:", premium)
    print("折价套利:", discount)
