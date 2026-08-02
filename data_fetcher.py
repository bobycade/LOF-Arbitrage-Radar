"""
LOF套利雷达 - 数据采集模块 v6.0
修复:
1. 使用 LSJZ API 获取申购状态（SGZT/SHZT字段），不再爬网页
2. 获取净值日期（FSRQ），区分iNAV和NAV
3. 获取申购限额信息
4. [v6.0] NAV/iNAV 采集改线程池并发；requests.get 直连避免 Session 线程安全问题
5. [v6.0] 折价套利赎回费默认 1.5%（T+1 赎回，持有<7天惩罚性费率）
6. [v6.0] 法定节假日休市判断；结果附带当日成交额 amount
"""
import requests
import json
import re
import os
import time
import logging
import concurrent.futures
from datetime import datetime

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


def is_market_closed(now):
    """判断指定时刻是否休市（周末或法定节假日）"""
    return now.weekday() >= 5 or now.strftime('%Y-%m-%d') in HOLIDAYS


class DataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://fund.eastmoney.com/',
        })
        self._lof_cache = None
        self._lof_cache_time = None

    def get_all_lof_list(self):
        """获取全部LOF基金列表"""
        if self._lof_cache and (datetime.now() - self._lof_cache_time).seconds < 3600:
            return self._lof_cache
        try:
            resp = self.session.get('https://fund.eastmoney.com/js/fundcode_search.js', timeout=30)
            match = re.search(r'var\s+r\s*=\s*(\[.*\])\s*;', resp.text.strip(), re.DOTALL)
            if not match:
                return self._lof_cache or []
            all_funds = json.loads(match.group(1))
            lof_list = []
            for item in all_funds:
                name_raw = str(item[2])
                # 通过名称中的(LOF)标识筛选，覆盖所有代码前缀（16/501/502/00等）
                if '(LOF)' not in name_raw.upper():
                    continue
                code = str(item[0])
                name = name_raw.replace('(LOF)', '').replace('(lof)', '').replace('(后端)', '')
                ftype = item[3] if len(item) > 3 else ''
                cat = self._classify(ftype, name)
                if cat:
                    lof_list.append({'code': code, 'name': name, 'type': cat})
            self._lof_cache = lof_list
            self._lof_cache_time = datetime.now()
            logger.info(f"LOF列表: {len(lof_list)} 只")
            return lof_list
        except Exception as e:
            logger.error(f"LOF列表失败: {e}")
            return self._lof_cache or []

    def _classify(self, ftype, name=''):
        """基金分类"""
        text = ftype + name
        if 'QDII' in text or '港股' in text or '美股' in text or '海外' in text:
            return 'QDII'
        if '商品' in text or '黄金' in text or '原油' in text or '白银' in text or '大宗' in text:
            return '商品'
        if '债券' in text or '货币' in text:
            return None
        if '混合' in text:
            return '混合'
        return '股票'

    def get_market_prices_batch(self, fund_codes):
        """批量获取场内实时价格（东方财富 ulist.np 批量接口）"""
        prices = {}
        batch_size = 100
        for i in range(0, len(fund_codes), batch_size):
            batch = fund_codes[i:i + batch_size]
            secids = []
            for code in batch:
                m = '1' if code.startswith('5') else '0'
                secids.append(f'{m}.{code}')

            secids_str = ','.join(secids)
            url = f'https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&fields=f2,f3,f4,f5,f6,f12,f14,f15,f16,f17&secids={secids_str}'
            try:
                resp = self.session.get(url, timeout=15)
                data = resp.json()
                if data.get('data') and data['data'].get('diff'):
                    for item in data['data']['diff']:
                        code = item.get('f12', '')
                        price = item.get('f2')
                        if price and float(price) > 0:
                            # f2=最新价, f3=涨跌幅%, f4=涨跌额, f5=成交量, f6=成交额
                            # f16=最高, f17=最低
                            prices[code] = {
                                'price': float(price),
                                'change_pct': float(item.get('f3', 0) or 0),
                                'volume': item.get('f5', 0),
                                'amount': item.get('f6', 0),
                                'high': float(item.get('f16', 0) or 0),
                                'low': float(item.get('f17', 0) or 0),
                            }
            except Exception as e:
                logger.error(f"批量价格获取失败(batch {i}): {e}")
            time.sleep(0.3)
        return prices

    def get_fund_nav_info(self, fund_code):
        """通过 LSJZ API 获取基金净值信息，包含申购状态和净值日期
        返回: dict with nav, nav_date, acc_nav, nav_change_pct, purchase_status, redemption_status, is_inav
        注意: 使用 requests.get 直连（headers 内联），不用 self.session —— 供线程池并发调用
        """
        try:
            url = f'https://api.fund.eastmoney.com/f10/lsjz?fundCode={fund_code}&pageIndex=1&pageSize=1'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://fundf10.eastmoney.com/',
            }
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            if data.get('Data') and data['Data'].get('LSJZList'):
                item = data['Data']['LSJZList'][0]
                return {
                    'nav': float(item.get('DWJZ', 0) or 0),
                    'acc_nav': float(item.get('LJJZ', 0) or 0),
                    'nav_date': item.get('FSRQ', ''),  # 净值日期
                    'nav_change_pct': float(item.get('JZZZL', 0) or 0),  # 净值涨跌幅%
                    'purchase_status': item.get('SGZT', ''),  # 申购状态
                    'redemption_status': item.get('SHZT', ''),  # 赎回状态
                    'nav_type': item.get('NAVTYPE', ''),  # 净值类型
                    'is_inav': False,  # 这是历史净值，不是iNAV
                }
        except Exception as e:
            logger.debug(f"NAV API失败 {fund_code}: {e}")
        return None

    def get_inav(self, fund_code):
        """获取盘中实时估值 iNAV（仅交易时间有效）
        返回: dict with inav, inav_date, inav_time, is_inav=True
        注意: 使用 requests.get 直连（headers 内联），不用 self.session —— 供线程池并发调用
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            resp = requests.get(f'http://fundgz.1234567.com.cn/js/{fund_code}.js', headers=headers, timeout=10)
            text = resp.text
            match = re.search(r'"gsz":"([\d.]+)"', text)
            if match:
                inav = float(match.group(1))
                # 解析估值时间
                gztime = ''
                time_match = re.search(r'"gztime":"([\d-: ]+)"', text)
                if time_match:
                    gztime = time_match.group(1)
                # 解析估值日期
                jzrq = ''
                jzrq_match = re.search(r'"jzrq":"([\d-]+)"', text)
                if jzrq_match:
                    jzrq = jzrq_match.group(1)
                return {
                    'nav': inav,
                    'nav_date': jzrq,
                    'inav_time': gztime,
                    'is_inav': True,
                }
        except:
            pass
        return None

    def fetch_all_data(self, fund_list=None):
        """采集全部基金数据
        交易时间: 优先用iNAV（盘中估值），否则用历史净值
        非交易时间: 使用最新历史净值
        """
        if not fund_list:
            fund_list = self.get_all_lof_list()
        if not fund_list:
            return []

        results = []
        start_time = time.time()

        # Step 1: 批量获取场内价格
        codes = [f['code'] for f in fund_list]
        logger.info(f"批量获取 {len(codes)} 只基金场内价格...")
        prices = self.get_market_prices_batch(codes)
        logger.info(f"获取到 {len(prices)} 只价格")

        # Step 2: 批量获取NAV信息（包含申购状态和净值日期）
        # 用 LSJZ API 一次性获取净值+申购状态（v6.0: 线程池并发）
        logger.info("获取净值和申购状态（并发）...")
        nav_info_map = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_code = {executor.submit(self.get_fund_nav_info, code): code for code in codes}
            for i, future in enumerate(concurrent.futures.as_completed(future_to_code)):
                code = future_to_code[future]
                try:
                    info = future.result()
                    if info and info.get('nav', 0) > 0:
                        nav_info_map[code] = info
                except Exception as e:
                    logger.debug(f"NAV获取失败 {code}: {e}")
                if (i + 1) % 50 == 0:
                    logger.info(f"NAV进度: {i + 1}/{len(codes)}")

        logger.info(f"获取到 {len(nav_info_map)} 只NAV信息")

        # Step 3: 获取iNAV（盘中估值，仅在交易时间有效）
        now = datetime.now()
        is_trading_time = (not is_market_closed(now) and
                           ((9, 30) <= (now.hour, now.minute) <= (11, 30) or
                            (13, 0) <= (now.hour, now.minute) <= (15, 0)))

        inav_map = {}
        if is_trading_time:
            logger.info("交易时间内，获取iNAV（并发）...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_code = {executor.submit(self.get_inav, code): code for code in codes}
                for i, future in enumerate(concurrent.futures.as_completed(future_to_code)):
                    code = future_to_code[future]
                    try:
                        inav = future.result()
                        if inav and inav.get('nav', 0) > 0:
                            inav_map[code] = inav
                    except Exception as e:
                        logger.debug(f"iNAV获取失败 {code}: {e}")
                    if (i + 1) % 50 == 0:
                        logger.info(f"iNAV进度: {i + 1}/{len(codes)}")
            logger.info(f"获取到 {len(inav_map)} 只iNAV")

        # Step 4: 合并数据
        for fund in fund_list:
            code = fund['code']
            price_info = prices.get(code)
            nav_info = nav_info_map.get(code)
            
            if not price_info or not nav_info:
                continue

            market_price = price_info['price']
            nav = nav_info['nav']
            nav_date = nav_info['nav_date']

            # 确定使用iNAV还是NAV
            inav_info = inav_map.get(code)
            if inav_info:
                ref_nav = inav_info['nav']
                is_inav = True
                inav_time = inav_info.get('inav_time', '')
                display_date = nav_date + ' ' + inav_time if inav_time else nav_date
            else:
                ref_nav = nav
                is_inav = False
                inav_time = ''
                display_date = nav_date

            if not ref_nav or ref_nav <= 0:
                continue

            # 计算溢价率/折价率
            premium_rate = round((market_price - ref_nav) / ref_nav * 100, 2)
            discount_rate = round((ref_nav - market_price) / ref_nav * 100, 2)

            # 解析申购状态
            sgzt = nav_info.get('purchase_status', '')
            shzt = nav_info.get('redemption_status', '')
            purchase_status, purchase_limit = self._parse_purchase_status(sgzt)
            redemption_status = self._parse_redemption_status(shzt)

            # 费率（默认值，实际费率因基金而异）
            # A类: 申购费 0.12%~1.5%, 赎回费随持有时间递减
            # 这里用保守估计
            purchase_fee = 0.0012  # 0.12%（大部分LOF申购费1折后约0.12%）
            if fund['type'] == 'QDII':
                purchase_fee = 0.0015  # QDII略高

            results.append({
                'code': code,
                'name': fund['name'],
                'type': fund['type'],
                'market_price': round(market_price, 4),
                'market_change_pct': round(price_info.get('change_pct', 0), 2),
                'nav': round(nav, 4),          # 最新收盘净值
                'nav_date': nav_date,           # 净值日期
                'inav': round(ref_nav, 4),      # 参考净值（交易时间=iNAV，非交易时间=NAV）
                'is_inav': is_inav,             # 是否为盘中估值
                'inav_time': inav_time,         # 估值时间
                'premium_rate': premium_rate,
                'discount_rate': discount_rate,
                'purchase_status': purchase_status,
                'purchase_limit': purchase_limit,
                'redemption_status': redemption_status,
                'purchase_fee': purchase_fee,
                'redemption_fee': 0.015,  # 折价套利为"场内买入→T+1即赎回"，持有期<7天，适用1.5%惩罚性赎回费
                'amount': price_info.get('amount', 0),  # 当日成交额，0 表示无成交（可能停牌）
                'data_date': display_date,
                'nav_change_pct': round(nav_info.get('nav_change_pct', 0), 2),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })

        elapsed = time.time() - start_time
        logger.info(f"采集完成: {len(results)}只, 耗时{elapsed:.1f}秒")
        return results

    @staticmethod
    def _parse_purchase_status(sgzt):
        """解析申购状态
        返回: (status_text, limit_amount)
        """
        if not sgzt:
            return '未知', 0
        
        if '暂停' in sgzt or '封闭' in sgzt:
            return '暂停申购', 0
        if '限大额' in sgzt or '限制大额' in sgzt:
            # 尝试提取限额金额
            m = re.search(r'(\d+\.?\d*)\s*(万|元)', sgzt)
            if m:
                amount = float(m.group(1))
                unit = m.group(2)
                if unit == '万':
                    amount *= 10000
                return '限制大额', int(amount)
            return '限制大额', 10000  # 默认1万
        if '开放' in sgzt:
            return '开放申购', 999999999
        
        return sgzt, 0

    @staticmethod
    def _parse_redemption_status(shzt):
        """解析赎回状态"""
        if not shzt:
            return '未知'
        if '暂停' in shzt or '封闭' in shzt:
            return '暂停赎回'
        if '限大额' in shzt or '限制大额' in shzt:
            return '限制大额赎回'
        if '开放' in shzt:
            return '开放赎回'
        return shzt
