"""
LOF套利雷达 - 用户认证模块 v2.0
提供：注册、登录、登出、权限装饰器
支持用户名/邮箱登录，Flask session 认证
[v2.0] 新增 admin_required 装饰器 / 操作日志记录辅助函数
"""
import functools
import logging
from flask import session, jsonify, redirect, url_for, request, g

logger = logging.getLogger(__name__)


# ==================== 权限装饰器 ====================

def login_required(f):
    """要求登录的装饰器 — 返回 401 JSON（给 API 用）"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # 如果是 API 请求返回 JSON
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'error': '需要登录后才能访问',
                    'need_login': True
                }), 401
            # 页面请求跳转登录页
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def login_optional(f):
    """可选登录装饰器 — 不强制登录，但会设置 g.current_user"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        g.current_user = None
        if 'user_id' in session:
            from database import DatabaseManager
            db = DatabaseManager()
            user = db.get_user_by_id(session['user_id'])
            if user:
                g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """要求超级管理员权限的装饰器（v5.0 新增）"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'error': '需要管理员权限'
                }), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== 登录/登出工具函数 ====================

def do_login(user_dict):
    """执行登录：写入 session"""
    session.clear()
    session.permanent = True
    session['user_id'] = user_dict['id']
    session['username'] = user_dict['username']
    session['nickname'] = user_dict.get('nickname') or user_dict['username']
    session['role'] = user_dict.get('role', 'free')
    logger.info(f"用户 {user_dict['username']} 已登录 (session={session.get('user_id')})")


def do_logout():
    """执行登出：清除 session"""
    username = session.get('username', '未知用户')
    session.clear()
    logger.info(f"用户 {username} 已登出")


def get_current_user():
    """获取当前登录用户信息（从 DB 实时读取）"""
    if 'user_id' not in session:
        return None
    from database import DatabaseManager
    db = DatabaseManager()
    return db.get_user_by_id(session['user_id'])


def is_logged_in():
    """检查是否已登录"""
    return 'user_id' in session


def is_vip():
    """检查是否为 VIP 用户"""
    return session.get('role') in ('vip', 'admin')


def is_admin():
    """检查是否为超级管理员"""
    return session.get('role') == 'admin'


# ==================== 操作日志辅助 (v5.0) ====================

def log_action(action, target_type=None, target_id=None, detail=''):
    """便捷操作日志记录（自动获取当前用户信息和IP）"""
    try:
        from database import DatabaseManager
        db = DatabaseManager()
        db.add_log(
            user_id=session.get('user_id'),
            username=session.get('username', 'system'),
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else ''
        )
    except Exception as e:
        logger.error(f"记录操作日志失败: {e}")
