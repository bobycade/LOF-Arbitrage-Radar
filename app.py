"""
LOF套利雷达 - Flask后端应用 v6.0
修复:
1-9. (v1-v3 历史修复)
10. [v4.0] 新增用户认证系统（注册/登录/登出）
11. [v4.0] 宽松访问模式：未登录可预览，详细数据+导出需登录
12. [v5.0] 管理后台（用户管理 / 系统配置 / 操作日志）
13. [v5.0] 操作审计日志
14. [v6.0] 告警字段补全 + 邮件 from 修复（P0 告警从未发出）
15. [v6.0] /api/refresh 需内部令牌/admin 身份 + 后台线程异步执行
16. [v6.0] SECRET_KEY 无公开默认值；session 生命周期不再全局污染
17. [v6.0] 告警去重状态持久化（重启不重复告警）；DatabaseManager 单例
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, g
import logging
import os
import json
import re
import threading
import time
import requests as http_requests
from datetime import datetime, timedelta, timezone
from data_fetcher import DataFetcher
from arbitrage_calculator import ArbitrageCalculator
from database import get_db
from auth import login_required, login_optional, do_login, do_logout, get_current_user, is_logged_in, admin_required, log_action
from notifier import Notifier
from dotenv import load_dotenv

# 加载配置
load_dotenv('.env')
load_dotenv('config.env')  # 兼容旧配置

# 配置日志（前置，后续模块级初始化需要 logger）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['JSON_AS_ASCII'] = False
# [v6.0] SECRET_KEY 不再提供公开默认值：未配置时生成临时随机密钥（重启后所有 session 失效）
_secret = os.getenv('SECRET_KEY', '')
if not _secret:
    logger.warning('⚠️ 未配置 SECRET_KEY，已生成临时随机密钥（重启后所有 session 失效）。请在 .env 中配置固定强随机值！')
    _secret = os.urandom(32).hex()
app.config['SECRET_KEY'] = _secret
# Session 持久时间：默认1天，记住我则7天
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# [v6.0] 内部接口令牌：scheduler 等内部调用方访问 /api/refresh 时携带
INTERNAL_TOKEN = os.getenv('INTERNAL_TOKEN', '')
if not INTERNAL_TOKEN:
    logger.warning('⚠️ 未配置 INTERNAL_TOKEN，/api/refresh 仅允许 admin 会话访问。建议在 .env 中配置！')

# 初始化组件
data_fetcher = DataFetcher()
calculator = ArbitrageCalculator()
db = get_db()

# 初始化推送器
wechat_webhook = os.getenv('WECHAT_WEBHOOK', '')
mail_config = None
if os.getenv('SMTP_USER') and os.getenv('SMTP_PASSWORD'):
    mail_config = {
        'server': os.getenv('SMTP_HOST', 'smtp.qq.com'),
        'port': int(os.getenv('SMTP_PORT', '587')),
        'user': os.getenv('SMTP_USER'),
        'password': os.getenv('SMTP_PASSWORD'),
        'from': os.getenv('SMTP_USER'),
        'to': os.getenv('EMAIL_TO', os.getenv('SMTP_USER'))
    }
notifier = Notifier(wechat_webhook, mail_config)

# 已推送的基金（v6.0: 持久化到数据库，重启后不重复告警）
def _load_alerted_funds():
    """从数据库恢复告警去重状态，解析失败回退空集合"""
    try:
        raw = db.get_config('alerted_funds', '')
        if raw:
            return set(json.loads(raw))
    except Exception as e:
        logger.warning(f"恢复告警去重状态失败，回退空集合: {e}")
    return set()


alerted_funds = _load_alerted_funds()

# 全局数据刷新状态
refresh_status = {'last_refresh': None, 'refreshing': False, 'count': 0, 'nav_date': ''}


@app.route('/')
@login_optional
def index():
    """主页 — 宽松模式：不强制登录，但登录后体验更好"""
    user = getattr(g, 'current_user', None)
    return render_template('index.html', user=user)


@app.route('/api/status')
def api_status():
    """系统状态接口（公开）"""
    try:
        total_funds = 0
        premium_count = 0
        discount_count = 0
        nav_date = ''
        try:
            import sqlite3
            conn = sqlite3.connect(db.db_path)
            c = conn.cursor()
            c.execute('SELECT COUNT(DISTINCT fund_code) FROM premium_history')
            total_funds = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM premium_history WHERE id IN (SELECT MAX(id) FROM premium_history GROUP BY fund_code) AND net_premium_return>=1.5")
            premium_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM premium_history WHERE id IN (SELECT MAX(id) FROM premium_history GROUP BY fund_code) AND net_discount_return>=1.5")
            discount_count = c.fetchone()[0]
            c.execute("SELECT nav_date FROM premium_history ORDER BY timestamp DESC LIMIT 1")
            row = c.fetchone()
            if row and row[0]:
                nav_date = row[0]
            conn.close()
        except:
            pass

        return jsonify({
            'success': True,
            'last_refresh': refresh_status.get('last_refresh'),
            'refreshing': refresh_status.get('refreshing', False),
            'total_funds': total_funds,
            'premium_count': premium_count,
            'discount_count': discount_count,
            'nav_date': nav_date or refresh_status.get('nav_date', ''),
            'logged_in': is_logged_in(),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 认证相关路由 ====================

@app.route('/login')
def login():
    """渲染登录页"""
    if is_logged_in():
        return redirect(url_for('index'))
    return render_template('login.html',
                           error=request.args.get('error'),
                           default_username=request.args.get('username', ''),
                           next_url=request.args.get('next'))


@app.route('/register')
def register():
    """渲染注册页"""
    if is_logged_in():
        return redirect(url_for('index'))
    return render_template('register.html',
                           error=request.args.get('error'))


@app.route('/api/login', methods=['POST'])
def api_login():
    """API: 用户登录"""
    try:
        data = request.get_json()
        login_name = data.get('login_name', '').strip()
        password = data.get('password', '')
        remember = data.get('remember', True)

        if not login_name or not password:
            return jsonify({'success': False, 'error': '请填写用户名和密码'})

        user = db.authenticate_user(login_name, password)
        if not user:
            return jsonify({'success': False, 'error': '用户名/邮箱或密码错误'})

        do_login(user)

        # session 持久时间（仅设置当前会话；全局 PERMANENT_SESSION_LIFETIME 配置不可在此修改）
        session.permanent = remember

        logger.info(f"用户 {user['username']} 登录成功")

        log_action('login', 'user', user['id'], f"用户 {user['username']} 登录成功")

        return jsonify({
            'success': True,
            'message': '登录成功',
            'user': {
                'id': user['id'],
                'username': user['username'],
                'nickname': user.get('nickname') or user['username'],
                'role': user.get('role', 'free')
            }
        })

    except Exception as e:
        logger.error(f"登录失败: {e}")
        return jsonify({'success': False, 'error': f'服务器内部错误: {str(e)}'}), 500


@app.route('/api/register', methods=['POST'])
def api_register():
    """API: 用户注册"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        nickname = data.get('nickname', '').strip() or None

        # 基本校验
        if not username or not password:
            return jsonify({'success': False, 'error': '请填写用户名和密码'})
        if len(username) < 4 or len(username) > 20:
            return jsonify({'success': False, 'error': '用户名需要4-20个字符'})
        if not username.replace('_', '').isalnum():
            return jsonify({'success': False, 'error': '用户名只能包含字母、数字和下划线'})
        if len(password) < 6:
            return jsonify({'success': False, 'error': '密码至少需要6个字符'})

        success, error_msg = db.create_user(username, email, password, nickname)
        if not success:
            return jsonify({'success': False, 'error': error_msg})

        logger.info(f"新用户注册成功: {username}")

        log_action('register', 'user', None, f"新用户注册: {username}")
        return jsonify({'success': True, 'message': '注册成功，请登录'})

    except Exception as e:
        logger.error(f"注册失败: {e}")
        return jsonify({'success': False, 'error': f'服务器内部错误'}), 500


@app.route('/api/logout')
def api_logout():
    """API: 用户登出"""
    do_logout()
    return jsonify({'success': True, 'message': '已退出登录'})


@app.route('/api/auth/check')
def api_auth_check():
    """API: 检查登录状态（前端轮询用）"""
    user = get_current_user()
    if not user:
        return jsonify({
            'success': True,
            'logged_in': False,
            'user': None
        })
    return jsonify({
        'success': True,
        'logged_in': True,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'nickname': user.get('nickname') or user['username'],
            'role': user.get('role', 'free')
        }
    })


@app.route('/api/user/profile')
@login_required
def api_user_profile():
    """API: 获取当前用户信息"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': '未登录'}), 401
    return jsonify({'success': True, 'data': user})


@app.route('/api/user/profile', methods=['POST'])
@login_required
def api_update_profile():
    """API: 更新用户资料（昵称、邮箱）"""
    try:
        data = request.get_json()
        nickname = data.get('nickname', '').strip() or None
        email = data.get('email', '').strip() or None

        success, error_msg = db.update_user_profile(
            session['user_id'], nickname=nickname, email=email
        )
        if not success:
            return jsonify({'success': False, 'error': error_msg})

        return jsonify({'success': True, 'message': '资料更新成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/password', methods=['PUT'])
@login_required
def api_change_password():
    """API: 修改密码"""
    try:
        data = request.get_json()
        old_pwd = data.get('old_password', '')
        new_pwd = data.get('new_password', '')

        if len(new_pwd) < 6:
            return jsonify({'success': False, 'error': '新密码至少6个字符'})

        success, error_msg = db.update_password(session['user_id'], old_pwd, new_pwd)
        if not success:
            return jsonify({'success': False, 'error': error_msg})

        return jsonify({'success': True, 'message': '密码修改成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 用户自选相关路由 ====================

@app.route('/api/favorites')
@login_required
def api_get_favorites():
    """获取我的自选列表"""
    favorites = db.get_favorites(session['user_id'])

    # 合并最新基金数据
    all_data = db.get_all_funds()
    # 注意 get_all_funds 返回的键是别名 code/name/type（非 fund_code）
    fund_map = {f['code']: f for f in all_data}

    enriched = []
    for fav in favorites:
        code = fav['fund_code']
        base = dict(fav)  # 转为普通 dict，避免 Row 序列化问题
        if code in fund_map:
            fd = fund_map[code]
            enriched.append({
                **base,
                'nav_date': fd.get('nav_date', ''),
                'market_price': fd.get('market_price'),
                'nav': fd.get('nav'),
                'premium_rate': fd.get('premium_rate') or fd.get('discount_rate') or '-',
                'profit_after_fee': fd.get('profit_after_fee') or fd.get('discount_profit') or 0,
                'purchase_status': fd.get('purchase_status', ''),
                'redeem_status': fd.get('redeem_status', '') or fd.get('redemption_status', ''),
            })
        else:
            enriched.append(base)

    return jsonify({'success': True, 'data': enriched})


@app.route('/api/favorites', methods=['POST'])
@login_required
def api_add_favorite():
    """添加自选"""
    data = request.get_json()
    fund_code = data.get('fund_code', '')
    fund_name = data.get('fund_name', '')
    fund_type = data.get('fund_type', '')

    if not fund_code:
        return jsonify({'success': False, 'error': '缺少基金代码'})

    db.add_favorite(session['user_id'], fund_code, fund_name, fund_type)
    return jsonify({'success': True, 'message': '已添加到自选'})


@app.route('/api/favorites/<fund_code>', methods=['DELETE'])
@login_required
def api_remove_favorite(fund_code):
    """取消自选"""
    db.remove_favorite(session['user_id'], fund_code)
    return jsonify({'success': True, 'message': '已从自选移除'})


def _check_refresh_auth():
    """校验 /api/refresh 调用方身份：内部令牌 或 admin 会话。
    INTERNAL_TOKEN 未配置时仅允许 admin 会话（启动时已 warning 提醒配置）。"""
    if INTERNAL_TOKEN and request.headers.get('X-Internal-Token', '') == INTERNAL_TOKEN:
        return True
    return session.get('role') == 'admin'


def _do_refresh_job():
    """后台刷新任务主体（内部维护 refresh_status，异常兜底复位 refreshing）"""
    global refresh_status
    try:
        logger.info("开始刷新数据...")

        # 获取LOF列表
        lof_list = data_fetcher.get_all_lof_list()
        if not lof_list:
            logger.error("LOF列表为空")
            return

        # 获取实时数据
        fund_data_list = data_fetcher.fetch_all_data(lof_list)
        if not fund_data_list:
            logger.error("无有效数据，可能非交易时间或接口异常")
            return

        # 计算套利
        fund_data_list = calculator.calculate_all(fund_data_list)

        # 存入数据库
        db.insert_data(fund_data_list)

        # 检查告警
        check_alerts(fund_data_list)

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 获取净值日期
        nav_date = fund_data_list[0].get('nav_date', '') if fund_data_list else ''
        refresh_status['last_refresh'] = now
        refresh_status['count'] = len(fund_data_list)
        refresh_status['nav_date'] = nav_date

        logger.info(f"数据刷新完成，共 {len(fund_data_list)} 只基金，净值日期 {nav_date}")

    except Exception as e:
        logger.error(f"刷新数据失败: {e}")
    finally:
        refresh_status['refreshing'] = False


@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """手动/定时刷新数据（v6.0: 需内部令牌或 admin 身份，后台线程异步执行）"""
    if not _check_refresh_auth():
        logger.warning(f"/api/refresh 未授权访问被拒绝 (ip={request.remote_addr})")
        return jsonify({'success': False, 'error': '无权限访问'}), 403

    if refresh_status.get('refreshing', False):
        return jsonify({
            'success': False,
            'error': '正在刷新中，请稍后重试',
            'refreshing': True
        })

    refresh_status['refreshing'] = True
    threading.Thread(target=_do_refresh_job, daemon=True).start()
    return jsonify({'success': True, 'message': '刷新任务已启动', 'refreshing': True})


@app.route('/api/premium')
def get_premium_funds():
    """获取溢价榜单 — 宽松模式：未登录返回前20条预览"""
    try:
        limit = int(request.args.get('limit', 200))
        fund_type = request.args.get('type', '')
        # 未登录限制预览数量
        if not is_logged_in() and limit > 30:
            limit = 30
        funds = db.get_all_premium_funds(limit, fund_type or None)

        nav_date = ''
        if funds:
            nav_date = funds[0].get('nav_date', '')

        # 未登录时隐藏部分敏感字段
        if not is_logged_in():
            for f in funds:
                f['purchase_limit'] = None
                # 标记为预览数据
                f['_preview'] = True

        return jsonify({
            'success': True,
            'data': funds,
            'nav_date': nav_date,
            'logged_in': is_logged_in(),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        logger.error(f"获取溢价榜单失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/discount')
def get_discount_funds():
    """获取折价榜单 — 宽松模式：未登录返回前20条预览"""
    try:
        limit = int(request.args.get('limit', 200))
        # 未登录限制预览数量
        if not is_logged_in() and limit > 30:
            limit = 30
        funds = db.get_all_discount_funds(limit)

        nav_date = ''
        if funds:
            nav_date = funds[0].get('nav_date', '')

        if not is_logged_in():
            for f in funds:
                f['purchase_limit'] = None
                f['_preview'] = True

        return jsonify({
            'success': True,
            'data': funds,
            'nav_date': nav_date,
            'logged_in': is_logged_in(),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        logger.error(f"获取折价榜单失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/qdii')
def get_qdii_funds():
    """获取QDII基金列表 — 宽松模式：未登录返回前20条预览"""
    try:
        limit = int(request.args.get('limit', 200))
        fund_type = request.args.get('type', '')
        if not is_logged_in() and limit > 30:
            limit = 30
        funds = db.get_qdii_funds(limit, fund_type or None)

        nav_date = ''
        if funds:
            nav_date = funds[0].get('nav_date', '')

        if not is_logged_in():
            for f in funds:
                f['_preview'] = True

        return jsonify({
            'success': True,
            'data': funds,
            'nav_date': nav_date,
            'logged_in': is_logged_in(),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        logger.error(f"获取QDII榜单失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/fund_types')
def get_fund_types():
    """获取基金分类列表"""
    try:
        include_qdii = request.args.get('qdii', '0') == '1'
        types = db.get_fund_types(include_qdii)
        return jsonify({
            'success': True,
            'data': types,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        logger.error(f"获取基金分类失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history/<fund_code>')
def get_history(fund_code):
    """获取基金历史数据 — 需要登录"""
    if not is_logged_in():
        return jsonify({'success': False, 'error': '需要登录后查看历史数据', 'need_login': True}), 401
    try:
        days = int(request.args.get('days', 7))
        # 免费用户限制7天，VIP可查看更多
        if session.get('role') != 'vip' and days > 30:
            days = 30
        history = db.get_history(fund_code, days)

        return jsonify({
            'success': True,
            'data': history
        })

    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/funds')
def get_all_funds():
    """获取所有基金（支持搜索）"""
    try:
        keyword = request.args.get('keyword', '')
        funds = db.get_all_funds()

        if keyword:
            funds = [f for f in funds if keyword.lower() in f.get('name', '').lower() or keyword in f.get('code', '')]

        return jsonify({
            'success': True,
            'data': funds,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        logger.error(f"获取基金列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search')
def search_funds():
    """搜索基金 — 宽松模式：未登录限制10条"""
    try:
        keyword = request.args.get('keyword', '')
        if not keyword or len(keyword) < 1:
            return jsonify({'success': True, 'data': [], 'count': 0})

        funds = db.get_all_funds()
        results = []
        for f in funds:
            fname = f.get('name', '')
            fcode = f.get('code', '')
            if keyword.lower() in fname.lower() or keyword in fcode:
                results.append(f)

        # 未登录限制结果数
        if not is_logged_in() and len(results) > 15:
            results = results[:15]

        return jsonify({
            'success': True,
            'data': results,
            'count': len(results),
            'logged_in': is_logged_in()
        })

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def check_alerts(fund_data_list):
    """检查并发送告警"""
    global alerted_funds
    threshold = float(os.getenv('ARBITRAGE_THRESHOLD_ALERT', '3.0'))

    alert_premium = []
    alert_discount = []

    for fund in fund_data_list:
        try:
            prem = fund.get('premium_arbitrage', {})
            if isinstance(prem, dict) and prem.get('net_return', 0) >= threshold:
                fund_key = f"{fund['code']}_premium"
                if fund_key not in alerted_funds:
                    alert_premium.append({
                        'code': fund['code'], 'name': fund['name'], 'type': fund.get('type', ''),
                        'market_price': fund.get('market_price', 0), 'inav': fund.get('inav', 0),
                        'premium_rate': fund.get('premium_rate', 0), 'discount_rate': fund.get('discount_rate', 0),
                        'net_return': prem.get('net_return', 0),
                        'purchase_status': fund.get('purchase_status', '未知'),
                        'suggestion': prem.get('suggestion', ''),
                    })
                    alerted_funds.add(fund_key)

            disc = fund.get('discount_arbitrage', {})
            if isinstance(disc, dict) and disc.get('net_return', 0) >= threshold:
                fund_key = f"{fund['code']}_discount"
                if fund_key not in alerted_funds:
                    alert_discount.append({
                        'code': fund['code'], 'name': fund['name'], 'type': fund.get('type', ''),
                        'market_price': fund.get('market_price', 0), 'inav': fund.get('inav', 0),
                        'premium_rate': fund.get('premium_rate', 0), 'discount_rate': fund.get('discount_rate', 0),
                        'net_return': disc.get('net_return', 0),
                        'purchase_status': fund.get('purchase_status', '未知'),
                        'suggestion': disc.get('suggestion', ''),
                    })
                    alerted_funds.add(fund_key)
        except Exception as e:
            logger.error(f"检查告警{fund.get('code')}失败: {e}")
            continue

    if alert_premium:
        try:
            notifier.send_arbitrage_alert(alert_premium, 'premium')
            logger.info(f"发送了 {len(alert_premium)} 条溢价告警")
        except Exception as e:
            logger.error(f"发送溢价告警失败: {e}")

    if alert_discount:
        try:
            notifier.send_arbitrage_alert(alert_discount, 'discount')
            logger.info(f"发送了 {len(alert_discount)} 条折价告警")
        except Exception as e:
            logger.error(f"发送折价告警失败: {e}")

    # 清理已过期告警
    current_codes = set()
    for fund in fund_data_list:
        prem = fund.get('premium_arbitrage', {})
        disc = fund.get('discount_arbitrage', {})
        if isinstance(prem, dict) and prem.get('net_return', 0) >= threshold:
            current_codes.add(f"{fund['code']}_premium")
        if isinstance(disc, dict) and disc.get('net_return', 0) >= threshold:
            current_codes.add(f"{fund['code']}_discount")
    alerted_funds = alerted_funds.intersection(current_codes)

    # v6.0: 持久化告警去重状态，重启后不重复告警
    try:
        db.set_config('alerted_funds', json.dumps(list(alerted_funds)))
    except Exception as e:
        logger.error(f"持久化告警去重状态失败: {e}")


# ==================== 基金详情代理接口 (v5.1) ====================
# 解决前端直接调东方财富 API 的 CORS 跨域问题

@app.route('/api/fund/detail')
def api_fund_detail():
    """代理获取基金详情：基本信息 + 近期业绩 + 基金经理"""
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'error': '缺少基金代码'}), 400

    result = {'code': code, 'basic': {}, 'performance': {}, 'manager': ''}
    # 必须使用 iPhone UA，否则 API 返回"网络繁忙"
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
        'Referer': 'https://mpservice.com/',
    }
    api_base = 'https://fundmobapi.eastmoney.com/FundMNewApi'
    params = 'FCODE={}&deviceid=Wap&version=2.0.0&product=EFund&plat=iPhone&osVersion=16.6&appType=iPhone'

    # 1) 基本信息
    try:
        url1 = f'{api_base}/FundMNNBasicInformation?{params.format(code)}'
        r1 = http_requests.get(url1, headers=headers, timeout=10)
        r1.raise_for_status()
        d1 = r1.json().get('Datas') or {}
        result['basic'] = {
            'name': d1.get('SHORTNAME', ''),
            'type': d1.get('FTYPE', ''),
            'setup_date': (d1.get('ESTABDATE') or d1.get('ISSEDATE') or ''),
            'scale': d1.get('ENDNAV', ''),
            'company': d1.get('JJGS', ''),
            'index_name': d1.get('INDEXNAME', ''),
            'purchase_rate': d1.get('RATE', ''),
            'source_rate': d1.get('SOURCERATE', ''),
            'cycle': d1.get('CYCLE', ''),
            'risk_level': d1.get('RISKLEVEL', ''),
            'yzba': d1.get('YZBA', ''),
            'bench': d1.get('BENCH', ''),
            'sgzt': d1.get('SGZT', ''),
            'shzt': d1.get('SHZT', ''),
        }
        # 基本信息接口本身也包含近一周收益率
        syl_z = d1.get('SYL_Z')
        if syl_z and syl_z != '--':
            result['performance']['1w'] = syl_z
    except Exception as e:
        logger.warning(f'基金详情-基本信息失败 {code}: {e}')

    # 2) 近期业绩
    try:
        url2 = f'{api_base}/FundMNPeriodIncrease?{params.format(code)}'
        r2 = http_requests.get(url2, headers=headers, timeout=10)
        r2.raise_for_status()
        items = r2.json().get('Datas') or []
        title_map = {'Z': '1w', 'Y': '1m', '3Y': '3m', '6Y': '6m', '1N': '1y', '3N': '3y', 'LN': 'all'}
        perf = result['performance']
        if isinstance(items, list):
            for item in items:
                key = title_map.get(item.get('title', ''))
                if key:
                    perf[key] = item.get('syl', '')
        result['performance'] = perf
    except Exception as e:
        logger.warning(f'基金详情-业绩数据失败 {code}: {e}')

    # 3) 基金经理
    try:
        url3 = f'{api_base}/FundMNInverstPosition?{params.format(code)}'
        r3 = http_requests.get(url3, headers=headers, timeout=10)
        r3.raise_for_status()
        d3 = r3.json().get('Datas')
        if isinstance(d3, list) and len(d3) > 0:
            managers = [x.get('MANAGERNAME', '') for x in d3 if x.get('MANAGERNAME')]
            result['manager'] = '、'.join(managers)
        elif isinstance(d3, dict) and d3.get('MANAGERNAME'):
            result['manager'] = d3['MANAGERNAME']
    except Exception as e:
        logger.warning(f'基金详情-基金经理失败 {code}: {e}')

    return jsonify({'success': True, 'data': result})


# [v6.1] 历史净值全量缓存：避免用户反复打开基金详情打爆东财接口
_nav_history_cache = {}  # {code: (fetched_at_epoch, response_dict)}
_nav_history_cache_lock = threading.Lock()
_NAV_HISTORY_CACHE_TTL = 300  # 5 分钟


def _fetch_nav_history_pingzhongdata(code: str):
    """从天天基金 pingzhongdata 接口拉取全量历史净值。

    解析页面 JS 中的两个变量：
      - Data_netWorthTrend: [{"x": 毫秒时间戳, "y": 单位净值, "equityReturn": 日涨幅%, ...}, ...]
      - Data_ACWorthTrend:  [[毫秒时间戳, 累计净值], ...]（可能不存在，容错处理）
    返回与东财 lsjz 接口字段兼容的列表（前端 _fdBuildNavRow 依赖），按日期倒序（最新在前）；
    请求失败或解析不到数据时返回 None，由调用方回退。
    """
    url = f'http://fund.eastmoney.com/pingzhongdata/{code}.js'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'http://fund.eastmoney.com/{code}.html',
    }
    r = http_requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    text = r.text

    # 单位净值走势（必需）
    m = re.search(r'var\s+Data_netWorthTrend\s*=\s*(\[.*?\])\s*;', text, re.S)
    if not m:
        return None
    net_worth_trend = json.loads(m.group(1))
    if not isinstance(net_worth_trend, list) or not net_worth_trend:
        return None

    # 累计净值走势（可选）：{毫秒时间戳: 累计净值}
    ac_map = {}
    m2 = re.search(r'var\s+Data_ACWorthTrend\s*=\s*(\[.*?\])\s*;', text, re.S)
    if m2:
        try:
            ac_trend = json.loads(m2.group(1))
            for pair in ac_trend:
                if isinstance(pair, list) and len(pair) >= 2:
                    ac_map[pair[0]] = pair[1]
        except Exception as e:
            logger.warning(f'累计净值走势解析失败 {code}: {e}')

    rows = []
    for item in net_worth_trend:
        if not isinstance(item, dict):
            continue
        ts = item.get('x')
        nav = item.get('y')
        if ts is None or nav is None:
            continue
        # 东财时间戳为北京时间零点：先按 UTC 换算再 +8h，避免依赖服务器本地时区
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc) + timedelta(hours=8)
        fsrq = dt.strftime('%Y-%m-%d')
        dwjz = f'{nav:.4f}' if isinstance(nav, (int, float)) else str(nav)
        ac_nav = ac_map.get(ts)
        # 无累计净值数据时回退等于单位净值
        ljjz = f'{ac_nav:.4f}' if isinstance(ac_nav, (int, float)) else dwjz
        equity_return = item.get('equityReturn')
        jzzzl = f'{equity_return:.2f}' if isinstance(equity_return, (int, float)) else ''
        rows.append({'FSRQ': fsrq, 'DWJZ': dwjz, 'LJJZ': ljjz, 'JZZZL': jzzzl})

    if not rows:
        return None
    # 前端约定"后端已按最新在前排列"
    rows.sort(key=lambda row: row['FSRQ'], reverse=True)
    return rows


def _nav_history_lsjz(code: str, page: int, page_size: int):
    """东财 lsjz 分页接口（旧实现，保留为分页兼容分支 / pingzhongdata 失败时的 fallback）"""
    try:
        url = f'https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex={page}&pageSize={page_size}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://fund.eastmoney.com/',
        }
        r = http_requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        return jsonify({
            'success': True,
            'data': data.get('Data', {}),
            'totalCount': data.get('TotalCount', 0),
        })
    except Exception as e:
        logger.warning(f'基金历史净值获取失败 {code}: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/fund/nav_history')
def api_fund_nav_history():
    """代理获取历史净值（解决跨域问题）。

    默认走 pingzhongdata 一次返回全量数据（带 5 分钟内存缓存）；
    显式传 page/pageSize 参数时走旧 lsjz 分页分支（兼容旧前端）；
    pingzhongdata 失败时自动回退 lsjz，保证接口可用性。
    """
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'error': '缺少基金代码'}), 400

    # 分页兼容分支：旧前端显式携带分页参数时使用旧逻辑
    page_param = request.args.get('page')
    page_size_param = request.args.get('pageSize')
    if page_param is not None or page_size_param is not None:
        # 非法分页参数（如 page=abc）回退默认值，避免 int() 抛 ValueError 变 500
        try:
            page = int(page_param or 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(page_size_param or 120)
        except (TypeError, ValueError):
            page_size = 120
        return _nav_history_lsjz(code, page, page_size)

    # 命中 5 分钟缓存直接返回
    now = time.time()
    with _nav_history_cache_lock:
        cached = _nav_history_cache.get(code)
    if cached and now - cached[0] < _NAV_HISTORY_CACHE_TTL:
        return jsonify(cached[1])

    # 主路径：pingzhongdata 全量
    try:
        rows = _fetch_nav_history_pingzhongdata(code)
        if rows:
            resp = {'success': True, 'data': {'LSJZList': rows}, 'totalCount': len(rows)}
            with _nav_history_cache_lock:
                _nav_history_cache[code] = (now, resp)
            return jsonify(resp)
        logger.warning(f'pingzhongdata 无有效净值数据，回退 lsjz: {code}')
    except Exception as e:
        logger.warning(f'pingzhongdata 历史净值失败 {code}，回退 lsjz: {e}')

    # fallback：lsjz 分页（首页 120 条）
    return _nav_history_lsjz(code, 1, 120)


# ==================== 管理后台路由 (v5.0) ====================

@app.route('/admin')
@admin_required
def admin_dashboard():
    """管理后台 - 仪表盘"""
    stats = db.get_stats()
    configs = db.get_all_configs()
    recent_logs = db.get_logs(limit=10)
    return render_template('admin/dashboard.html',
                           user=get_current_user(),
                           stats=stats,
                           configs=configs,
                           recent_logs=recent_logs)


@app.route('/admin/users')
@admin_required
def admin_users():
    """管理后台 - 用户列表"""
    page = int(request.args.get('page', 1))
    keyword = request.args.get('keyword', '').strip()
    result = db.get_all_users(page=page, per_page=20, keyword=keyword)
    return render_template('admin/users.html',
                           user=get_current_user(),
                           users=result,
                           keyword=keyword)


@app.route('/admin/user/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    """管理后台 - 用户详情/编辑页"""
    target_user = db.get_user_for_admin(user_id)
    if not target_user:
        return redirect(url_for('admin_users'))
    return render_template('admin/edit_user.html',
                           user=get_current_user(),
                           target=target_user)


@app.route('/admin/config')
@admin_required
def admin_config():
    """管理后台 - 系统配置"""
    configs = db.get_all_configs()
    return render_template('admin/config.html',
                           user=get_current_user(),
                           configs=configs)


@app.route('/admin/logs')
@admin_required
def admin_logs():
    """管理后台 - 操作日志"""
    action = request.args.get('action', '')
    limit = int(request.args.get('limit', 100))
    logs = db.get_logs(limit=limit, action=action or None)
    return render_template('admin/logs.html',
                           user=get_current_user(),
                           logs=logs,
                           action_filter=action)


# ==================== 管理后台 API (v5.0) ====================

@app.route('/api/admin/stats')
@admin_required
def api_admin_stats():
    """API: 获取仪表盘统计数据（AJAX刷新用）"""
    stats = db.get_stats()
    return jsonify({'success': True, 'data': stats})


@app.route('/api/admin/users')
@admin_required
def api_admin_users():
    """API: 获取用户列表(JSON)"""
    page = int(request.args.get('page', 1))
    keyword = request.args.get('keyword', '').strip()
    result = db.get_all_users(page=page, per_page=20, keyword=keyword)
    return jsonify({'success': True, 'data': result})


@app.route('/api/admin/user/<int:user_id>', methods=['POST'])
@admin_required
def api_admin_update_user(user_id):
    """API: 管理员更新用户信息"""
    try:
        data = request.get_json()
        success, error = db.admin_update_user(user_id, **data)
        if not success:
            return jsonify({'success': False, 'error': error})

        # 记录日志
        detail = f"更新用户 {user_id} 信息: {list(data.keys())}"
        log_action('update_user', 'user', user_id, detail)

        return jsonify({'success': True, 'message': '用户信息已更新'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/user/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def api_admin_reset_password(user_id):
    """API: 管理员重置用户密码"""
    try:
        data = request.get_json()
        new_password = data.get('password', '')
        if len(new_password) < 6:
            return jsonify({'success': False, 'error': '密码至少6个字符'})

        success, error = db.admin_reset_password(user_id, new_password)
        if not success:
            return jsonify({'success': False, 'error': error})

        log_action('reset_password', 'user', user_id, f"重置了用户 {user_id} 的密码")
        return jsonify({'success': True, 'message': f'密码已重置为: {new_password}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/user/<int:user_id>/ban', methods=['POST'])
@admin_required
def api_admin_ban_user(user_id):
    """API: 封禁/解封用户"""
    try:
        data = request.get_json()
        ban = data.get('ban', True)  # True=封禁, False=解封

        if ban:
            # 默认封禁30天
            days = int(data.get('days', 30))
            banned_until = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            success, error = db.admin_update_user(user_id, is_active=0, banned_until=banned_until)
            action_text = f"封禁{days}天"
        else:
            success, error = db.admin_update_user(user_id, is_active=1, banned_until=None)
            action_text = "解除封禁"

        if not success:
            return jsonify({'success': False, 'error': error})

        log_action(f'{"ban" if ban else "unban"}_user', 'user', user_id, f"{action_text} 用户 {user_id}")
        return jsonify({'success': True, 'message': f'已{action_text}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/user/<int:user_id>/role', methods=['POST'])
@admin_required
def api_admin_change_role(user_id):
    """API: 更改用户角色"""
    try:
        data = request.get_json()
        new_role = data.get('role', 'free')
        if new_role not in ('free', 'vip', 'admin'):
            return jsonify({'success': False, 'error': '无效的角色'})

        success, error = db.admin_update_user(user_id, role=new_role)
        if not success:
            return jsonify({'success': False, 'error': error})

        log_action('change_role', 'user', user_id, f"将用户 {user_id} 角色改为 {new_role}")
        return jsonify({'success': True, 'message': f'角色已更改为 {new_role}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_user(user_id):
    """API: 软删除用户"""
    success, error = db.admin_soft_delete_user(user_id)
    if not success:
        return jsonify({'success': False, 'error': error})

    log_action('delete_user', 'user', user_id, f"软删除了用户 {user_id}")
    return jsonify({'success': True, 'message': '用户已删除'})


@app.route('/api/admin/user/<int:user_id>/restore', methods=['POST'])
@admin_required
def api_admin_restore_user(user_id):
    """API: 恢复被软删除的用户"""
    success, error = db.admin_restore_user(user_id)
    if not success:
        return jsonify({'success': False, 'error': error})

    log_action('restore_user', 'user', user_id, f"恢复了用户 {user_id}")
    return jsonify({'success': True, 'message': '用户已恢复'})


@app.route('/api/admin/config', methods=['POST'])
@admin_required
def api_admin_update_config():
    """API: 批量更新系统配置"""
    try:
        data = request.get_json()
        updates = data.get('configs', {})
        results = []
        for key, value in updates.items():
            ok = db.set_config(key, value, updated_by=session.get('user_id'))
            results.append({'key': key, 'ok': ok})
            if ok:
                log_action('update_config', 'config', None, f'修改配置: {key} = {value}')

        failed = [r['key'] for r in results if not r['ok']]
        if failed:
            return jsonify({
                'success': False,
                'error': f'部分配置更新失败: {", ".join(failed)}'
            })

        return jsonify({'success': True, 'message': f'已更新 {len(results)} 项配置'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/logs')
@admin_required
def api_admin_logs():
    """API: 获取操作日志(JSON)"""
    action = request.args.get('action', '')
    limit = int(request.args.get('limit', 100))
    logs = db.get_logs(limit=limit, action=action or None)
    return jsonify({'success': True, 'data': logs})


host = os.getenv('FLASK_HOST', '0.0.0.0')
port = int(os.getenv('FLASK_PORT', '5000'))
debug = os.getenv('DEBUG', 'false').lower() == 'true'

if __name__ == '__main__':
    logger.info(f"LOF套利雷达启动，访问地址: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
