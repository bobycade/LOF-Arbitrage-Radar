"""
LOF套利雷达 - 数据库管理模块 v5.0
修复:
1-9. (v1-v3 历史修复)
10. [v4.0] 新增 users / user_favorites 用户认证表
11. [v5.0] 操作日志表 / 系统配置表 / 邮箱验证表
12. [v5.0] users表扩展字段(手机号/头像/备注)
13. [v5.0] 数据库迁移机制(自动ALTER TABLE)
14. [v5.0] 用户管理方法(CRUUD/角色/封禁/重置密码/软删除)
15. [v6.0] premium_history 去重 + (fund_code, nav_date) 唯一索引，INSERT OR REPLACE 真正生效
16. [v6.0] set_config 支持插入新 key；新增进程级单例 get_db()
"""
import sqlite3
from datetime import datetime, timedelta
import logging
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

# 数据库版本号，用于迁移判断
DB_VERSION = 6


class DatabaseManager:

    def __init__(self, db_path='lof_data.db'):
        self.db_path = db_path
        self.init_database()
        self.run_migrations()

    def init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS premium_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fund_code TEXT NOT NULL,
                fund_name TEXT,
                fund_type TEXT,
                market_price REAL,
                market_change_pct REAL DEFAULT 0,
                nav REAL,
                nav_date TEXT,
                inav REAL,
                is_inav INTEGER DEFAULT 0,
                inav_time TEXT DEFAULT '',
                premium_rate REAL,
                discount_rate REAL,
                purchase_status TEXT DEFAULT '未知',
                purchase_limit INTEGER DEFAULT 0,
                redemption_status TEXT DEFAULT '未知',
                net_premium_return REAL DEFAULT 0,
                net_discount_return REAL DEFAULT 0,
                nav_change_pct REAL DEFAULT 0,
                data_date TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_code ON premium_history(fund_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ts ON premium_history(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_type ON premium_history(fund_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nav_date ON premium_history(nav_date)')

        # ========== 用户表 (v4.0) ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nickname TEXT,
                role TEXT DEFAULT 'free',
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                login_count INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')

        # ========== 用户自选表 (v4.0) ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                fund_code TEXT NOT NULL,
                fund_name TEXT,
                fund_type TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, fund_code)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fav_user ON user_favorites(user_id)')

        # ========== 操作日志表 (v5.0) ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id INTEGER,
                detail TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_user ON operation_logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_action ON operation_logs(action)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_time ON operation_logs(created_at)')

        # ========== 系统配置表 (v5.0) ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER
            )
        ''')

        # ========== 邮箱验证码表 (v5.0) — 预留 ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                purpose TEXT DEFAULT 'register',
                used INTEGER DEFAULT 0,
                expires_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_verify ON email_verifications(email)')

        # ========== 初始化默认系统配置 ==========
        default_configs = [
            ('site_name', 'LOF套利雷达', '站点名称'),
            ('allow_register', '1', '是否开放注册(1=开放 0=关闭)'),
            ('guest_preview_limit', '30', '游客可预览的数据条数'),
            ('vip_price_monthly', '29.9', 'VIP月费价格(元)'),
            ('vip_price_yearly', '299', 'VIP年费价格(元)'),
            ('alert_threshold', '3.0', '告警阈值(%)'),
            ('show_threshold', '1.5', '展示阈值(%)'),
            ('maintenance_mode', '0', '维护模式(1=开启 0=关闭)'),
            ('announcement', '', '站点公告(HTML支持)'),
        ]
        cursor.executemany(
            '''INSERT OR IGNORE INTO system_config (key, value, description) VALUES (?, ?, ?)''',
            default_configs
        )

        conn.commit()
        conn.close()

    def insert_data(self, fund_data_list):
        """批量插入数据（同一天同基金只保留最新一条（v6 起真正生效：
        唯一索引 idx_unique_fund_navdate(fund_code, nav_date) 使 INSERT OR REPLACE 命中冲突覆盖旧行））"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            inserted = 0

            for fund in fund_data_list:
                try:
                    prem = fund.get('premium_arbitrage', {})
                    disc = fund.get('discount_arbitrage', {})
                    net_prem = prem.get('net_return', 0) if isinstance(prem, dict) else 0
                    net_disc = disc.get('net_return', 0) if isinstance(disc, dict) else 0

                    # 处理限额：0表示暂停/未知，超大数表示不限
                    limit_val = fund.get('purchase_limit', 0)
                    if limit_val >= 999999999:
                        limit_val = -1  # -1表示不限

                    cursor.execute('''
                        INSERT OR REPLACE INTO premium_history
                        (fund_code, fund_name, fund_type, market_price, market_change_pct,
                         nav, nav_date, inav, is_inav, inav_time,
                         premium_rate, discount_rate, purchase_status, purchase_limit,
                         redemption_status, net_premium_return, net_discount_return,
                         nav_change_pct, data_date, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        fund['code'], fund['name'], fund['type'],
                        fund.get('market_price', 0),
                        fund.get('market_change_pct', 0),
                        fund.get('nav', 0),
                        fund.get('nav_date', ''),
                        fund.get('inav', 0),
                        1 if fund.get('is_inav', False) else 0,
                        fund.get('inav_time', ''),
                        fund.get('premium_rate', 0),
                        fund.get('discount_rate', 0),
                        fund.get('purchase_status', '未知'),
                        limit_val,
                        fund.get('redemption_status', '未知'),
                        round(net_prem, 2), round(net_disc, 2),
                        fund.get('nav_change_pct', 0),
                        fund.get('data_date', ''),
                        current_time
                    ))
                    inserted += 1
                except Exception as e:
                    logger.error(f"插入{fund.get('code')}失败: {e}")
                    continue

            conn.commit()
            conn.close()
            logger.info(f"插入 {inserted}/{len(fund_data_list)} 条数据")
        except Exception as e:
            logger.error(f"批量插入失败: {e}")

    def _get_latest_timestamp(self):
        """获取最新的数据时间戳"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(timestamp) FROM premium_history')
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] else None

    def _format_limit(self, limit_val):
        """格式化限额显示"""
        if limit_val is None or limit_val == 0:
            return '--'
        if limit_val == -1:
            return '不限'
        if limit_val >= 10000:
            return f'{limit_val / 10000:.0f}万'
        return f'{limit_val}'

    def get_top_premium_funds(self, limit=50):
        """获取溢价最高的基金（非QDII，净收益>=1.5%）"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT fund_code as code, fund_name as name, fund_type as type,
                       market_price, market_change_pct, nav, nav_date,
                       inav, is_inav, premium_rate,
                       net_premium_return as profit_after_fee,
                       purchase_status, purchase_limit, redemption_status as redeem_status,
                       data_date, nav_change_pct
                FROM premium_history
                WHERE id IN (SELECT MAX(id) FROM premium_history GROUP BY fund_code)
                AND fund_type != 'QDII'
                AND net_premium_return >= 1.5
                ORDER BY net_premium_return DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取溢价榜失败: {e}")
            return []

    def get_all_premium_funds(self, limit=200, fund_type=None):
        """获取全部非QDII的LOF基金，支持按fund_type二级筛选"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = '''
                SELECT fund_code as code, fund_name as name, fund_type as type,
                       market_price, market_change_pct, nav, nav_date,
                       inav, is_inav,
                       premium_rate, discount_rate,
                       net_premium_return as profit_after_fee,
                       net_discount_return as discount_profit,
                       purchase_status, purchase_limit, redemption_status as redeem_status,
                       data_date, nav_change_pct
                FROM premium_history
                WHERE id IN (SELECT MAX(id) FROM premium_history GROUP BY fund_code)
                AND fund_type != 'QDII'
            '''
            params = []
            if fund_type:
                sql += ' AND fund_type = ?'
                params.append(fund_type)
            sql += ' ORDER BY ABS(net_premium_return) DESC LIMIT ?'
            params.append(limit)

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取全部溢价失败: {e}")
            return []

    def get_top_discount_funds(self, limit=50):
        """获取折价最高的基金（非QDII，净收益>=1.5%）"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT fund_code as code, fund_name as name, fund_type as type,
                       market_price, market_change_pct, nav, nav_date,
                       inav, is_inav, discount_rate,
                       net_discount_return as profit_after_fee,
                       purchase_status, purchase_limit, redemption_status as redeem_status,
                       data_date, nav_change_pct
                FROM premium_history
                WHERE id IN (SELECT MAX(id) FROM premium_history GROUP BY fund_code)
                AND fund_type != 'QDII'
                AND net_discount_return >= 1.5
                ORDER BY net_discount_return DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取折价榜失败: {e}")
            return []

    def get_all_discount_funds(self, limit=200):
        """获取所有有折价的基金（非QDII）"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT fund_code as code, fund_name as name, fund_type as type,
                       market_price, market_change_pct, nav, nav_date,
                       inav, is_inav, discount_rate,
                       net_discount_return as profit_after_fee,
                       purchase_status, purchase_limit, redemption_status as redeem_status,
                       data_date, nav_change_pct
                FROM premium_history
                WHERE id IN (SELECT MAX(id) FROM premium_history GROUP BY fund_code)
                AND fund_type != 'QDII'
                AND discount_rate > 0
                ORDER BY net_discount_return DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取全部折价失败: {e}")
            return []

    def get_qdii_funds(self, limit=200, fund_type=None):
        """获取QDII型LOF基金，支持按fund_type二级筛选"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = '''
                SELECT fund_code as code, fund_name as name, fund_type as type,
                       market_price, market_change_pct, nav, nav_date,
                       inav, is_inav,
                       premium_rate, discount_rate,
                       net_premium_return as profit_after_fee,
                       net_discount_return as discount_profit,
                       purchase_status, purchase_limit, redemption_status as redeem_status,
                       data_date, nav_change_pct
                FROM premium_history
                WHERE id IN (SELECT MAX(id) FROM premium_history GROUP BY fund_code)
                AND fund_type = 'QDII'
            '''
            params = []
            if fund_type:
                sql += ' AND fund_type = ?'
                params.append(fund_type)
            sql += ' ORDER BY ABS(net_premium_return) DESC LIMIT ?'
            params.append(limit)

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取QDII失败: {e}")
            return []

    def get_history(self, fund_code, days=7):
        """获取基金历史数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                SELECT premium_rate, discount_rate, is_inav,
                       net_premium_return, net_discount_return,
                       data_date, timestamp
                FROM premium_history
                WHERE fund_code = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            ''', (fund_code, start_date))

            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取历史失败: {e}")
            return []

    def get_all_funds(self):
        """获取所有基金最新数据（字段名与前端统一）"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT fund_code AS code, fund_name AS name, fund_type AS type,
                       market_price, market_change_pct, nav, nav_date,
                       inav, is_inav, inav_time,
                       premium_rate, discount_rate,
                       net_premium_return AS profit_after_fee,
                       net_discount_return AS discount_profit,
                       purchase_status, purchase_limit,
                       redemption_status AS redeem_status,
                       nav_change_pct, data_date, timestamp
                FROM premium_history
                WHERE id IN (SELECT MAX(id) FROM premium_history GROUP BY fund_code)
            ''')
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取全部基金失败: {e}")
            return []

    def get_fund_types(self, include_qdii=False):
        """获取所有可用的fund_type分类及其数量"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            sql = '''
                SELECT fund_type, COUNT(*) as cnt
                FROM premium_history
                WHERE id IN (SELECT MAX(id) FROM premium_history GROUP BY fund_code)
                AND fund_type IS NOT NULL AND fund_type != ''
            '''
            if not include_qdii:
                sql += " AND fund_type != 'QDII'"
            sql += ' GROUP BY fund_type ORDER BY cnt DESC'

            cursor.execute(sql)
            rows = cursor.fetchall()
            conn.close()
            return [{'type': r[0], 'count': r[1]} for r in rows]
        except Exception as e:
            logger.error(f"获取基金分类失败: {e}")
            return []

    def clean_old_data(self, days=30):
        """清理旧数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('DELETE FROM premium_history WHERE timestamp < ?', (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"清理失败: {e}")
            return 0

    # ==================== 用户认证相关方法 (v4.0) ====================

    def create_user(self, username, email, password, nickname=None):
        """创建新用户，返回 (success, error_msg)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 检查用户名是否已存在
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                conn.close()
                return False, '用户名已存在'

            # 检查邮箱是否已存在
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                conn.close()
                return False, '邮箱已被注册'

            password_hash = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, nickname)
                VALUES (?, ?, ?, ?)
            ''', (username, email, password_hash, nickname or username))
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"新用户注册成功: {username} (id={user_id})")
            return True, None
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            return False, f'数据库错误: {str(e)}'

    def authenticate_user(self, login_name, password):
        """验证用户（支持用户名或邮箱登录），返回 user_dict 或 None"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, username, email, password_hash, nickname,
                       role, is_active, created_at, last_login, login_count
                FROM users WHERE (username = ? OR email = ?) AND is_active = 1
            ''', (login_name, login_name))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            if not check_password_hash(row['password_hash'], password):
                return None

            # 更新登录信息
            self._update_login_info(row['id'])

            return dict(row)

        except Exception as e:
            logger.error(f"验证用户失败: {e}")
            return None

    def _update_login_info(self, user_id):
        """更新用户登录时间和次数"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                UPDATE users SET last_login = ?, login_count = login_count + 1
                WHERE id = ?
            ''', (now, user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"更新登录信息失败: {e}")

    def get_user_by_id(self, user_id):
        """根据ID获取用户信息（不含密码）"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, email, nickname, role, is_active,
                       created_at, last_login, login_count
                FROM users WHERE id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    def get_user_by_username(self, username):
        """根据用户名获取用户信息（不含密码）"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, email, nickname, role, is_active,
                       created_at, last_login, login_count
                FROM users WHERE username = ?
            ''', (username,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    def update_user_profile(self, user_id, nickname=None, email=None):
        """更新用户资料"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            updates = []
            params = []
            if nickname:
                updates.append('nickname = ?')
                params.append(nickname)
            if email:
                updates.append('email = ?')
                params.append(email)
            if not updates:
                conn.close()
                return True, None

            params.append(user_id)
            sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
            return True, None
        except sqlite3.IntegrityError:
            return False, '该邮箱已被使用'
        except Exception as e:
            logger.error(f"更新用户资料失败: {e}")
            return False, str(e)

    def update_password(self, user_id, old_password, new_password):
        """修改密码"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 验证旧密码
            cursor.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            if not row or not check_password_hash(row[0], old_password):
                conn.close()
                return False, '原密码错误'

            new_hash = generate_password_hash(new_password)
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
            conn.commit()
            conn.close()
            logger.info(f"用户 {user_id} 已修改密码")
            return True, None
        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            return False, str(e)

    # ==================== 用户自选相关方法 (v4.0) ====================

    def add_favorite(self, user_id, fund_code, fund_name='', fund_type=''):
        """添加自选基金"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO user_favorites (user_id, fund_code, fund_name, fund_type)
                VALUES (?, ?, ?, ?)
            ''', (user_id, fund_code, fund_name, fund_type))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"添加自选失败: {e}")
            return False

    def remove_favorite(self, user_id, fund_code):
        """取消自选"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM user_favorites WHERE user_id = ? AND fund_code = ?',
                (user_id, fund_code)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"取消自选失败: {e}")
            return False

    def get_favorites(self, user_id):
        """获取用户的自选列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT fund_code, fund_name, fund_type, created_at
                FROM user_favorites WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取自选列表失败: {e}")
            return []

    # ==================== 数据库迁移机制 (v5.0) ====================

    def run_migrations(self):
        """运行数据库迁移（自动检测并执行）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 检查/创建版本表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS db_version (
                    version INTEGER PRIMARY KEY,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('SELECT MAX(version) FROM db_version')
            row = cursor.fetchone()
            current_version = row[0] if row and row[0] else 0

            if current_version < DB_VERSION:
                logger.info(f"数据库版本 {current_version} → {DB_VERSION}，开始迁移...")
                self._migrate(cursor, current_version)
                cursor.execute('INSERT OR REPLACE INTO db_version (version) VALUES (?)', (DB_VERSION,))
                conn.commit()
                logger.info(f"数据库迁移完成，当前版本: {DB_VERSION}")

            conn.close()
        except Exception as e:
            logger.error(f"数据库迁移失败: {e}")

    def _migrate(self, cursor, from_version):
        """执行具体的迁移步骤"""
        # v4→v5: users表扩展字段
        try:
            # 检查并添加 phone 字段
            cursor.execute("PRAGMA table_info(users)")
            columns = {row[1] for row in cursor.fetchall()}

            if 'phone' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN phone TEXT')
                logger.info("  迁移: users 表添加 phone 字段")

            if 'avatar' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ""')
                logger.info("  迁移: users 表添加 avatar 字段")

            if 'remark' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN remark TEXT DEFAULT ""')
                logger.info("  迁移: users 表添加 remark 字段(管理员备注)")

            if 'deleted_at' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN deleted_at DATETIME')
                logger.info("  迁移: users 表添加 deleted_at 字段(软删除)")

            if 'banned_until' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN banned_until DATETIME')
                logger.info("  迁移: users 表添加 banned_until 字段(封禁到期)")
        except Exception as e:
            logger.error(f"  迁移users表字段失败: {e}")

        # v5→v6: premium_history 去重并建立唯一索引，使 INSERT OR REPLACE 真正生效（幂等，可重复执行）
        try:
            # 1) 先去重：同一天同基金只保留 id 最大（最新）的一条
            cursor.execute('''
                DELETE FROM premium_history
                WHERE id NOT IN (
                    SELECT MAX(id) FROM premium_history GROUP BY fund_code, nav_date
                )
            ''')
            logger.info(f"  迁移: premium_history 历史数据去重，删除 {cursor.rowcount} 条重复记录")

            # 2) 再建唯一索引：fund_code + nav_date
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_fund_navdate
                ON premium_history(fund_code, nav_date)
            ''')
            logger.info("  迁移: premium_history 建立 (fund_code, nav_date) 唯一索引")
        except Exception as e:
            logger.error(f"  迁移premium_history唯一索引失败: {e}")

    # ==================== 操作日志 (v5.0) ====================

    def add_log(self, user_id, username, action, target_type=None, target_id=None,
                detail='', ip_address=None, user_agent=None):
        """记录操作日志"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO operation_logs
                (user_id, username, action, target_type, target_id, detail, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, action, target_type, target_id, detail,
                  ip_address, user_agent))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"记录操作日志失败: {e}")

    def get_logs(self, limit=100, action=None, user_id=None, start_date=None, end_date=None):
        """查询操作日志"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = '''
                SELECT l.*, u.username as operator_name, u.role as operator_role
                FROM operation_logs l
                LEFT JOIN users u ON l.user_id = u.id
                WHERE 1=1
            '''
            params = []
            if action:
                sql += ' AND l.action = ?'
                params.append(action)
            if user_id:
                sql += ' AND l.user_id = ?'
                params.append(user_id)
            if start_date:
                sql += ' AND l.created_at >= ?'
                params.append(start_date)
            if end_date:
                sql += ' AND l.created_at <= ?'
                params.append(end_date)

            sql += ' ORDER BY l.created_at DESC LIMIT ?'
            params.append(limit)

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"查询操作日志失败: {e}")
            return []

    # ==================== 系统配置 (v5.0) ====================

    def get_config(self, key, default=None):
        """获取单个系统配置"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM system_config WHERE key = ?', (key,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else default
        except Exception as e:
            logger.error(f"获取配置{key}失败: {e}")
            return default

    def get_all_configs(self):
        """获取所有系统配置"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM system_config ORDER BY key')
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取系统配置失败: {e}")
            return []

    def set_config(self, key, value, updated_by=None):
        """更新系统配置（key 不存在时自动插入新配置）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if updated_by is None:
                cursor.execute('''
                    UPDATE system_config SET value = ?, updated_at = ?
                    WHERE key = ?
                ''', (value, now, key))
            else:
                cursor.execute('''
                    UPDATE system_config SET value = ?, updated_at = ?, updated_by = ?
                    WHERE key = ?
                ''', (value, now, updated_by, key))
            # v6.0: UPDATE 命中 0 行说明是新 key，插入之（保留已有 key 的 description）
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO system_config (key, value, updated_at, updated_by)
                    VALUES (?, ?, ?, ?)
                ''', (key, value, now, updated_by))
            conn.commit()
            conn.close()
            logger.info(f"系统配置已更新: {key} = {value}")
            return True
        except Exception as e:
            logger.error(f"更新系统配置{key}失败: {e}")
            return False

    # ==================== 用户管理方法 (v5.0) ====================

    def get_all_users(self, include_deleted=False, page=1, per_page=20, keyword=''):
        """分页获取用户列表（管理后台用）"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            where = 'WHERE 1=1'
            params = []
            if not include_deleted:
                where += ' AND deleted_at IS NULL'
            if keyword:
                where += ' AND (username LIKE ? OR email LIKE ? OR nickname LIKE ?)'
                kw = f'%{keyword}%'
                params.extend([kw, kw, kw])

            # 总数
            count_sql = f'SELECT COUNT(*) FROM users {where}'
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            # 分页数据
            offset = (page - 1) * per_page
            data_sql = f'''
                SELECT id, username, email, nickname, role, phone,
                       is_active, created_at, last_login, login_count,
                       deleted_at, banned_until, remark
                FROM users {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            '''
            params.extend([per_page, offset])
            cursor.execute(data_sql, params)
            rows = cursor.fetchall()
            conn.close()

            return {
                'total': total,
                'page': page,
                'per_page': per_page,
                'data': [dict(r) for r in rows]
            }
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return {'total': 0, 'page': page, 'per_page': per_page, 'data': []}

    def get_user_for_admin(self, user_id):
        """管理员查看用户详情（含 remark/banned_until 等扩展字段）"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, email, nickname, role, phone, avatar,
                       is_active, created_at, last_login, login_count,
                       deleted_at, banned_until, remark
                FROM users WHERE id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取用户详情失败: {e}")
            return None

    def admin_update_user(self, user_id, **kwargs):
        """管理员更新用户信息（角色、状态、封禁、备注等）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            allowed_fields = {
                'role', 'nickname', 'email', 'phone', 'is_active',
                'banned_until', 'remark', 'deleted_at'
            }

            updates = []
            params = []
            for field, value in kwargs.items():
                if field in allowed_fields and value is not None:
                    updates.append(f'{field} = ?')
                    params.append(value)

            if not updates:
                conn.close()
                return True, None

            params.append(user_id)
            sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
            logger.info(f"管理员更新用户 {user_id}: {updates}")
            return True, None
        except sqlite3.IntegrityError as e:
            return False, str(e)
        except Exception as e:
            logger.error(f"管理员更新用户失败: {e}")
            return False, str(e)

    def admin_reset_password(self, user_id, new_password):
        """管理员重置用户密码"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            new_hash = generate_password_hash(new_password)
            cursor.execute(
                'UPDATE users SET password_hash = ? WHERE id = ?',
                (new_hash, user_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"管理员重置了用户 {user_id} 的密码")
            return True, None
        except Exception as e:
            logger.error(f"重置密码失败: {e}")
            return False, str(e)

    def admin_soft_delete_user(self, user_id):
        """软删除用户"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE users SET deleted_at = ?, is_active = 0 WHERE id = ?',
                (now, user_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"用户 {user_id} 已被软删除")
            return True, None
        except Exception as e:
            logger.error(f"软删除用户失败: {e}")
            return False, str(e)

    def admin_restore_user(self, user_id):
        """恢复被软删除的用户"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET deleted_at = NULL, is_active = 1 WHERE id = ?',
                (user_id,)
            )
            conn.commit()
            conn.close()
            logger.info(f"用户 {user_id} 已恢复")
            return True, None
        except Exception as e:
            logger.error(f"恢复用户失败: {e}")
            return False, str(e)

    def get_stats(self):
        """获取系统统计数据（仪表盘用）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            stats = {}

            # 用户统计
            cursor.execute('SELECT COUNT(*) FROM users WHERE deleted_at IS NULL')
            stats['total_users'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND role='admin'")
            stats['admin_count'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND role='vip'")
            stats['vip_count'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND role='free'")
            stats['free_count'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND is_active=1")
            stats['active_users'] = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM users WHERE deleted_at IS NOT NULL')
            stats['deleted_users'] = cursor.fetchone()[0]

            # 今日新增
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT COUNT(*) FROM users WHERE date(created_at)=? AND deleted_at IS NULL", (today,))
            stats['new_today'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE date(last_login)=? AND deleted_at IS NULL", (today,))
            stats['login_today'] = cursor.fetchone()[0]

            # 基金数据统计
            cursor.execute('SELECT COUNT(DISTINCT fund_code) FROM premium_history')
            stats['total_funds'] = cursor.fetchone()[0]

            # 最新数据时间
            cursor.execute('SELECT MAX(timestamp) FROM premium_history')
            row = cursor.fetchone()
            stats['last_data_time'] = row[0] if row and row[0] else ''

            # 自选总数
            cursor.execute('SELECT COUNT(*) FROM user_favorites')
            stats['total_favorites'] = cursor.fetchone()[0]

            # 日志条数(近7天)
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('SELECT COUNT(*) FROM operation_logs WHERE created_at >= ?', (week_ago,))
            stats['recent_logs'] = cursor.fetchone()[0]

            conn.close()
            return stats
        except Exception as e:
            logger.error(f"获取统计数据失败: {e}")
            return {}


# ==================== 进程级单例 (v6.0) ====================

_default_db = None


def get_db():
    """进程级单例，避免每请求重复初始化（init_database + migrations）。
    DatabaseManager 各方法内部均新建 sqlite 连接，单例本身无线程安全问题。"""
    global _default_db
    if _default_db is None:
        _default_db = DatabaseManager()
    return _default_db
