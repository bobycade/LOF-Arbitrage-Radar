// ========== 全局变量 ==========
let currentTab = 'premium';
let currentData = { premium: [], discount: [], qdii: [] };
let originalData = { premium: [], discount: [], qdii: [] };
let favorites = [];
let currentPage = { premium: 1, discount: 1, qdii: 1, favorites: 1 };
const REFRESH_INTERVAL = 300000; // 5分钟
let sortState = {
    premium: { key: null, direction: 'asc' },
    discount: { key: null, direction: 'asc' },
    qdii: { key: null, direction: 'asc' }
};

let notificationSettings = {
    enabled: false,
    premiumThreshold: 3.0,
    discountThreshold: 2.0,
    profitThreshold: 1.5,
    cooldownTime: 30
};
let lastNotificationTime = { premium: 0, discount: 0, profit: 0 };
let lastRefreshTime = 0;
let countdownTimer = null;

// ========== 用户认证状态 (v4.0) ==========
let currentUser = null;       // 当前登录用户信息
let isLoggedInState = false;   // 登录状态

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', function() {
    // 检测登录状态（最先执行）
    checkAuthStatus();

    loadSettings();
    loadFavorites();
    loadTheme();
    loadFundTypes();
    loadStatus();
    setInterval(loadStatus, REFRESH_INTERVAL);
    startCountdown();
});

// ========== 用户认证 (v4.0) ==========

async function checkAuthStatus() {
    try {
        const res = await fetch('/api/auth/check');
        const data = await res.json();
        if (data.success && data.logged_in) {
            currentUser = data.user;
            isLoggedInState = true;
            updateUserUI(true);
        } else {
            currentUser = null;
            isLoggedInState = false;
            updateUserUI(false);
        }
    } catch (e) {
        console.error('检查登录状态失败:', e);
        isLoggedInState = false;
        updateUserUI(false);
    }
}

function updateUserUI(loggedIn) {
    // 更新头部用户信息区
    const userArea = document.getElementById('userArea');
    if (!userArea) return;

    if (loggedIn && currentUser) {
        userArea.innerHTML = `
            <span class="user-avatar clickable" onclick="openProfile()" title="查看个人资料">${(currentUser.nickname || currentUser.username).charAt(0).toUpperCase()}</span>
            <span class="user-name clickable" onclick="openProfile()">${currentUser.nickname || currentUser.username}</span>
            ${currentUser.role === 'vip' ? '<span class="vip-badge">VIP</span>' : ''}
            ${currentUser.role === 'admin' ? '<a href="/admin" class="admin-link" title="管理后台">管理后台</a>' : ''}
            <button class="logout-btn" onclick="handleLogout()">退出</button>
        `;
        userArea.className = 'user-area logged-in';
    } else {
        userArea.innerHTML = `
            <button class="login-btn" onclick="showLogin()">登录</button>
            <button class="register-btn-sm" onclick="showRegister()">注册</button>
        `;
        userArea.className = 'user-area';
    }

    // 显示/隐藏自选标签（需要登录）
    const favTab = document.getElementById('favTab');
    if (favTab) favTab.style.display = loggedIn ? 'inline-block' : 'none';
}

function showLogin() {
    window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
}

function showRegister() {
    window.location.href = '/register';
}

async function handleLogout() {
    try {
        await fetch('/api/logout', { method: 'GET' });
        currentUser = null;
        isLoggedInState = false;
        showNotification('已退出登录', '');
        setTimeout(() => { window.location.reload(); }, 800);
    } catch (e) {
        console.error('登出失败:', e);
    }
}

// ======== Fetch 拦截器：401 自动跳转登录 ========
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const response = await originalFetch.apply(this, args);

    // 如果返回 401 且需要登录
    if (response.status === 401) {
        try {
            const data = await response.clone().json();
            if (data.need_login) {
                // 显示登录提示遮罩
                showLoginPrompt();
            }
        } catch (e) {
            // 非 JSON 响应，忽略
        }
    }

    return response;
};

function showLoginPrompt() {
    // 移除已有的
    const existing = document.getElementById('loginPromptOverlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'loginPromptOverlay';
    overlay.innerHTML = `
        <div class="login-prompt">
            <h3>🔐 需要登录</h3>
            <p>该功能需要登录后才能使用</p>
            <div class="prompt-actions">
                <button class="prompt-login" onclick="window.location.href='/login?next=' + encodeURIComponent(window.location.pathname)">立即登录</button>
                <button class="prompt-close" onclick="document.getElementById('loginPromptOverlay').remove()">稍后再说</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
}

// ========== 倒计时 ==========
function startCountdown() {
    if (countdownTimer) clearInterval(countdownTimer);
    lastRefreshTime = Date.now();
    countdownTimer = setInterval(updateCountdown, 1000);
}

function updateCountdown() {
    const elapsed = Date.now() - lastRefreshTime;
    const remaining = Math.max(0, REFRESH_INTERVAL - elapsed);
    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);
    const el = document.getElementById('nextRefresh');
    if (el) {
        el.textContent = `${minutes}分${seconds < 10 ? '0' : ''}${seconds}秒`;
    }
}

// ========== 标签页切换 ==========
function switchTab(tabName) {
    currentTab = tabName;
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(tabName).classList.add('active');

    if (tabName === 'search') return;
    if (tabName === 'favorites') { renderFavorites(); return; }
    if (currentData[tabName].length === 0) { loadData(tabName); }
    else { renderTable(tabName); }
}

// ========== 加载基金分类 ==========
async function loadFundTypes() {
    try {
        // 加载非QDII分类（给溢价和折价标签用）
        const res1 = await fetch('/api/fund_types');
        const r1 = await res1.json();
        if (r1.success && r1.data) {
            const sel1 = document.getElementById('premiumTypeFilter');
            r1.data.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.type;
                opt.textContent = `${t.type}（${t.count}只）`;
                sel1.appendChild(opt);
            });
        }
        // 加载QDII分类（给QDII标签用）
        const res2 = await fetch('/api/fund_types?qdii=1');
        const r2 = await res2.json();
        if (r2.success && r2.data) {
            const sel2 = document.getElementById('qdiiTypeFilter');
            r2.data.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.type;
                opt.textContent = `${t.type}（${t.count}只）`;
                sel2.appendChild(opt);
            });
        }
    } catch (e) {
        console.error('加载基金分类失败:', e);
    }
}

// ========== 加载数据 ==========
async function loadData(type) {
    try {
        let url = `/api/${type}?all=1`;
        // 溢价和QDII标签支持分类筛选
        const typeSelect = document.getElementById(`${type}TypeFilter`);
        if (typeSelect && typeSelect.value) {
            url += `&type=${encodeURIComponent(typeSelect.value)}`;
        }
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();
        const data = result.data || result || [];
        originalData[type] = [...data];
        currentData[type] = [...data];
        const filterCheckbox = document.getElementById(`${type}Filter`);
        if (filterCheckbox && filterCheckbox.checked) applyFilter(type, false);
        if (sortState[type].key) sortTable(type, sortState[type].key, false);
        renderTable(type);
        checkNotifications(type, data);
    } catch (error) {
        console.error(`加载${type}数据失败:`, error);
        const colSpan = type === 'qdii' || type === 'premium' ? 11 : 10;
        document.getElementById(`${type}TableBody`).innerHTML =
            `<tr><td colspan="${colSpan}" style="text-align:center;color:#f44336;">加载失败: ${error.message}</td></tr>`;
    }
}

// ========== 渲染表格（统一字段适配） ==========
function adaptItem(item) {
    // 统一字段名：后端可能用 redemption_status/redeem_status, net_return/profit_after_fee 等
    let profit = item.profit_after_fee ?? item.net_return ?? item.net_premium_return ?? item.net_discount_return ?? '-';
    if (profit !== '-') profit = parseFloat(profit) || 0;
    let discProfit = item.discount_profit ?? item.net_discount_return ?? '-';
    if (discProfit !== '-') discProfit = parseFloat(discProfit) || 0;
    return {
        ...item,
        redeem_status: item.redeem_status || item.redemption_status || '-',
        profit_after_fee: profit,
        discount_profit: discProfit,
        premium_rate: item.premium_rate ?? '-',
        discount_rate: item.discount_rate ?? '-',
    };
}

function renderTable(type) {
    const tableBody = document.getElementById(`${type}TableBody`);
    const data = currentData[type];
    if (!data || data.length === 0) {
        const colSpan = (type === 'qdii' || type === 'premium') ? 11 : 10;
        tableBody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align:center;color:#999;">暂无数据</td></tr>`;
        return;
    }

    tableBody.innerHTML = data.map(item => {
        const d = adaptItem(item);
        const pc = parseFloat(d.profit_after_fee) >= 0 ? 'profit-positive' : 'profit-negative';
        const isUnk = (d.purchase_status === '场内买入' || d.purchase_status === '限制大额') && !d.redemption_nav;
        const isFav = favorites.some(f => f.code === d.code);
        const favBtn = `<button class="favorite-btn" onclick="toggleFavorite('${d.code}','${esc(d.name)}','${d.type||''}','${d.nav_date||''}','${d.market_price||''}','${d.nav||''}','${d.premium_rate !== '-' ? d.premium_rate : d.discount_rate}','${d.profit_after_fee}','${d.purchase_status||''}','${d.redeem_status||''}',this)" title="${isFav?'取消关注':'添加关注'}">${isFav?'⭐':'☆'}</button>`;
        const statusHtml = isUnk
            ? `<span class="unknown-price" onclick="showRiskWarning('${d.code}','${esc(d.name)}')">赎回价未知</span>`
            : getStatusLabel(d.redeem_status);
        const calcBtn = `<button class="row-calc-btn" onclick="openCalculatorWith('${d.code}','${esc(d.name)}','${d.type||''}','${d.market_price||0}','${d.nav||0}','${d.premium_rate !== '-' ? d.premium_rate : d.discount_rate}','${d.profit_after_fee}','${d.purchase_status||''}','${d.redeem_status||''}')">计算</button>`;

        // 溢价和QDII都显示11列（溢价率 + 折价率分开）
        if (type === 'premium' || type === 'qdii') {
            return `<tr>
                <td>${favBtn} ${d.code||'-'}</td>
                <td>${d.name||'-'}</td>
                <td>${d.type||'-'}</td>
                <td>${d.nav_date||'-'}</td>
                <td>${d.market_price||'-'}</td>
                <td>${d.nav||'-'}</td>
                <td class="${parseFloat(d.premium_rate)>0?'profit-positive':'profit-negative'}">${d.premium_rate}%</td>
                <td class="${parseFloat(d.discount_rate)>0?'profit-positive':'profit-negative'}">${d.discount_rate}%</td>
                <td class="${pc}">${d.profit_after_fee}%${calcBtn}</td>
                <td>${getStatusLabel(d.purchase_status)}${_ggLink(d.code)}</td>
                <td>${statusHtml}</td>
            </tr>`;
        }
        // 折价标签10列
        return `<tr>
            <td>${favBtn} ${d.code||'-'}</td>
            <td>${d.name||'-'}</td>
            <td>${d.type||'-'}</td>
            <td>${d.nav_date||'-'}</td>
            <td>${d.market_price||'-'}</td>
            <td>${d.nav||'-'}</td>
            <td class="${pc}">${d.discount_rate}%</td>
            <td class="${pc}">${d.profit_after_fee}%${calcBtn}</td>
            <td>${getStatusLabel(d.purchase_status)}${_ggLink(d.code)}</td>
            <td>${statusHtml}</td>
        </tr>`;
    }).join('');
}

function esc(s) { return (s||'').replace(/'/g, "\\'"); }

// ========== 排序 ==========
function sortTable(type, key, render = true) {
    if (!originalData[type] || originalData[type].length === 0) return;
    if (sortState[type].key === key) sortState[type].direction = sortState[type].direction === 'asc' ? 'desc' : 'asc';
    else { sortState[type].key = key; sortState[type].direction = 'asc'; }
    document.querySelectorAll(`#${type} th`).forEach(th => th.classList.remove('sort-asc','sort-desc'));
    const th = document.querySelector(`#${type} th[data-sort="${key}"]`);
    if (th) th.classList.add(`sort-${sortState[type].direction}`);
    const numKeys = ['market_price','nav','premium_rate','discount_rate','profit_after_fee','net_return','net_premium_return','net_discount_return'];
    currentData[type].sort((a, b) => {
        const da = adaptItem(a), db = adaptItem(b);
        let av = da[key] ?? (key === 'profit_after_fee' ? (da.net_return ?? 0) : '');
        let bv = db[key] ?? (key === 'profit_after_fee' ? (db.net_return ?? 0) : '');
        if (numKeys.includes(key)) { av = parseFloat(av)||0; bv = parseFloat(bv)||0; }
        return sortState[type].direction === 'asc' ? (av>bv?1:-1) : (av<bv?1:-1);
    });
    if (render) renderTable(type);
}

// ========== 筛选 ==========
function applyFilter(type, render = true) {
    const fc = document.getElementById(`${type}Filter`);
    const sb = document.getElementById(`${type}Search`);
    if (!originalData[type]) return;
    let d = [...originalData[type]];
    if (fc && fc.checked) d = d.filter(i => { const a = adaptItem(i); return (a.purchase_status==='开放申购'||a.purchase_status==='场内买入')&&(a.redeem_status==='开放赎回'||a.redeem_status==='场内卖出'); });
    if (sb && sb.value.trim()) { const q = sb.value.trim().toLowerCase(); d = d.filter(i => (i.code&&i.code.toLowerCase().includes(q))||(i.name&&i.name.toLowerCase().includes(q))); }
    currentData[type] = d;
    if (render) renderTable(type);
}

// ========== CSV导出 ==========
function exportCSV(type) {
    let data, filename, headers;
    if (type === 'premium') { data = currentData.premium; filename = `溢价套利_${new Date().toLocaleDateString('zh-CN')}.csv`; headers = ['基金代码','基金名称','类型','净值日期','场内价格','参考净值','溢价率','扣费后收益','申购状态','赎回状态']; }
    else if (type === 'discount') { data = currentData.discount; filename = `折价套利_${new Date().toLocaleDateString('zh-CN')}.csv`; headers = ['基金代码','基金名称','类型','净值日期','场内价格','参考净值','折价率','扣费后收益','申购状态','赎回状态']; }
    else if (type === 'qdii') { data = currentData.qdii; filename = `QDII专区_${new Date().toLocaleDateString('zh-CN')}.csv`; headers = ['基金代码','基金名称','类型','净值日期','场内价格','参考净值','溢价率','折价率','扣费后收益','申购状态','赎回状态']; }
    else if (type === 'favorites') { data = favorites; filename = `我的自选_${new Date().toLocaleDateString('zh-CN')}.csv`; headers = ['基金代码','基金名称','类型','净值日期','场内价格','参考净值','溢价/折价率','扣费后收益','申购状态','赎回状态']; }
    if (!data || data.length === 0) { alert('暂无数据可导出'); return; }
    let csv = '\ufeff' + headers.join(',') + '\n';
    data.forEach(item => {
        const r = type === 'qdii' ?
            [item.code,item.name,item.type,item.nav_date,item.market_price,item.nav,item.premium_rate,item.discount_rate,item.profit_after_fee,item.purchase_status,item.redeem_status].map(escCSV).join(',') :
            type === 'favorites' ?
            [item.code,item.name,item.type,item.nav_date,item.market_price,item.nav,item.rate,item.profit_after_fee,item.purchase_status,item.redeem_status].map(escCSV).join(',') :
            [item.code,item.name,item.type,item.nav_date,item.market_price,item.nav,item.premium_rate||item.discount_rate,item.profit_after_fee,item.purchase_status,item.redeem_status].map(escCSV).join(',');
        csv += r + '\n';
    });
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showNotification('导出成功', `已导出 ${data.length} 条记录`);
}

function escCSV(v) {
    if (v === null || v === undefined) return '""';
    const s = String(v);
    return (s.includes(',') || s.includes('"') || s.includes('\n')) ? `"${s.replace(/"/g,'""')}"` : s;
}

// ========== 搜索 ==========
async function searchFund() {
    const q = document.getElementById('searchInput').value.trim();
    const rd = document.getElementById('searchResults');
    if (!q) { rd.innerHTML = '<p style="text-align:center;color:#999;">请输入基金代码或名称进行搜索</p>'; return; }
    rd.innerHTML = '<div class="loading">搜索中</div>';
    try {
        const res = await fetch(`/api/search?keyword=${encodeURIComponent(q)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const items = data.data || data || [];
        if (items.length === 0) { rd.innerHTML = '<p style="text-align:center;color:#999;">未找到相关基金</p>'; return; }
        rd.innerHTML = items.map(item => {
            const d = adaptItem(item);
            const pc = parseFloat(d.profit_after_fee) >= 0 ? 'profit-positive' : 'profit-negative';
            const isUnk = (d.purchase_status === '场内买入' || d.purchase_status === '限制大额') && !d.redemption_nav;
            const isFav = favorites.some(f => f.code === d.code);
            const rate = d.premium_rate !== '-' ? d.premium_rate : (d.discount_rate !== '-' ? d.discount_rate : '-');
            return `<div class="result-card">
                <h4>
                  <button class="favorite-btn" onclick="toggleFavorite('${d.code}','${esc(d.name)}','${d.type||''}','${d.nav_date||''}','${d.market_price||''}','${d.nav||''}','${rate}','${d.profit_after_fee}','${d.purchase_status||''}','${d.redeem_status||''}',this)">${isFav?'⭐':'☆'}</button>
                  <span class="fund-code-link" data-code="${d.code}" data-name="${esc(d.name)}" onclick="openFundDetail(this.dataset.code, currentData.premium.concat(currentData.discount,currentData.qdii).find(x=>x.code===this.dataset.code) || {code:this.dataset.code,name:this.dataset.name})">${d.code} - ${d.name}</span>
                </h4>
                <p><strong>类型:</strong> ${d.type||'-'} | <strong>净值日期:</strong> ${d.nav_date||'-'}</p>
                <p><strong>场内价格:</strong> ${d.market_price||'-'} | <strong>参考净值:</strong> ${d.nav||'-'}</p>
                <p><strong>溢价/折价率:</strong> <span class="${pc}">${rate}%</span> | <strong>扣费后收益:</strong> <span class="${pc}">${d.profit_after_fee}%</span></p>
                <p><strong>申购:</strong> ${getStatusLabel(d.purchase_status)}${_ggLink(d.code)} | <strong>赎回:</strong> ${isUnk?`<span class="unknown-price" onclick="showRiskWarning('${d.code}','${esc(d.name)}')">赎回价未知</span>`:getStatusLabel(d.redeem_status)}</p>
            </div>`;
        }).join('');
    } catch (e) { rd.innerHTML = `<p style="text-align:center;color:#f44336;">搜索失败: ${e.message}</p>`; }
}

// ========== 状态标签 ==========
/** 生成基金公告链接（申购/赎回状态原始出处） */
function _ggLink(code) {
    if (!code) return '';
    return `<a class="gg-link" href="https://fundf10.eastmoney.com/jjgg_${code}.html" target="_blank" rel="noopener" onclick="event.stopPropagation()" title="查看基金公告（申购/赎回状态原始出处）">↗</a>`;
}

function getStatusLabel(status) {
    if (!status) return '-';
    if (status.includes('开放')) return `<span class="status-open">${status}</span>`;
    if (status.includes('暂停') || status.includes('关闭')) return `<span class="status-closed">${status}</span>`;
    if (status.includes('场内')) return `<span class="status-partial">${status}</span>`;
    return status;
}

// ========== 加载状态 ==========
async function loadStatus() {
    const btn = document.getElementById('refreshBtn');
    const rs = document.getElementById('refreshStatus');
    const lu = document.getElementById('lastUpdate');
    try {
        btn.disabled = true;
        rs.textContent = '刷新中...';
        rs.className = 'refresh-status refreshing';
        const res = await fetch('/api/status');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const status = await res.json();
        if (status.is_refreshing || status.refreshing) {
            rs.textContent = '正在刷新中...';
            rs.className = 'refresh-status refreshing';
            setTimeout(loadStatus, 10000);
        } else {
            rs.textContent = '就绪';
            rs.className = 'refresh-status success';
            loadData('premium');
            loadData('discount');
            loadData('qdii');
            renderFavorites();
            lastRefreshTime = Date.now();
        }
        const updateTime = status.last_refresh || status.last_update;
        if (updateTime) lu.textContent = updateTime;
        else lu.textContent = '从未';
    } catch (e) {
        console.error('加载状态失败:', e);
        rs.textContent = '错误';
        rs.className = 'refresh-status error';
        lu.textContent = '加载失败';
        setTimeout(() => { rs.textContent = '-'; rs.className = 'refresh-status'; }, 15000);
    } finally { btn.disabled = false; }
}

function refreshData() { loadStatus(); }

// ========== 浏览器通知 ==========
function toggleSettings() {
    const p = document.getElementById('settingsPanel');
    const isHidden = p.style.display === 'none' || !p.style.display;
    p.style.display = isHidden ? 'flex' : 'none';
}

// 点击设置面板背景关闭
document.addEventListener('click', function(e) {
    if (e.target.id === 'settingsPanel') toggleSettings();
});

function toggleNotification() {
    const en = document.getElementById('enableNotif').checked;
    if (en && 'Notification' in window) {
        if (Notification.permission === 'default') {
            Notification.requestPermission().then(p => {
                if (p === 'granted') showNotification('通知已启用', 'LOF套利监控预警已开启');
                else { document.getElementById('enableNotif').checked = false; alert('请允许浏览器通知权限'); }
            });
        } else if (Notification.permission === 'denied') {
            document.getElementById('enableNotif').checked = false;
            alert('浏览器通知权限已被拒绝，请在浏览器设置中手动开启');
        }
    }
}

function saveSettings() {
    notificationSettings = {
        enabled: document.getElementById('enableNotif').checked,
        premiumThreshold: parseFloat(document.getElementById('premiumThreshold').value) || 3.0,
        discountThreshold: parseFloat(document.getElementById('discountThreshold').value) || 2.0,
        profitThreshold: parseFloat(document.getElementById('profitThreshold').value) || 1.5,
        cooldownTime: parseInt(document.getElementById('cooldownTime').value) || 30
    };
    localStorage.setItem('lofNotificationSettings', JSON.stringify(notificationSettings));
    toggleSettings();
    showNotification('设置已保存', '预警设置已更新');
}

function loadSettings() {
    const s = localStorage.getItem('lofNotificationSettings');
    if (s) notificationSettings = JSON.parse(s);
    document.getElementById('enableNotif').checked = notificationSettings.enabled;
    document.getElementById('premiumThreshold').value = notificationSettings.premiumThreshold;
    document.getElementById('discountThreshold').value = notificationSettings.discountThreshold;
    document.getElementById('profitThreshold').value = notificationSettings.profitThreshold;
    document.getElementById('cooldownTime').value = notificationSettings.cooldownTime;
}

function checkNotifications(type, data) {
    if (!notificationSettings.enabled || !('Notification' in window) || Notification.permission !== 'granted') return;
    const now = Date.now();
    const cd = notificationSettings.cooldownTime * 60000;
    if (type === 'premium') {
        const ops = data.filter(i => { const d = adaptItem(i); return parseFloat(d.premium_rate)>=notificationSettings.premiumThreshold && parseFloat(d.profit_after_fee)>=notificationSettings.profitThreshold && d.purchase_status==='开放申购' && d.redeem_status==='开放赎回'; });
        if (ops.length > 0 && now - lastNotificationTime.premium > cd) {
            const best = ops.reduce((p,c) => { const dp = adaptItem(p), dc = adaptItem(c); return parseFloat(dp.premium_rate)>parseFloat(dc.premium_rate)?p:c; });
            const bd = adaptItem(best);
            showNotification('🚀 溢价套利机会！', `${bd.code} ${bd.name} 溢价率${bd.premium_rate}%（收益${bd.profit_after_fee}%）`);
            lastNotificationTime.premium = now;
        }
    }
    if (type === 'discount') {
        const ops = data.filter(i => { const d = adaptItem(i); return parseFloat(d.discount_rate)>=notificationSettings.discountThreshold && parseFloat(d.profit_after_fee)>=notificationSettings.profitThreshold && !(d.purchase_status==='场内买入'&&!d.redemption_nav); });
        if (ops.length > 0 && now - lastNotificationTime.discount > cd) {
            const best = ops.reduce((p,c) => { const dp = adaptItem(p), dc = adaptItem(c); return parseFloat(dp.discount_rate)>parseFloat(dc.discount_rate)?p:c; });
            const bd = adaptItem(best);
            showNotification('💰 折价套利机会！', `${bd.code} ${bd.name} 折价率${bd.discount_rate}%（收益${bd.profit_after_fee}%）`);
            lastNotificationTime.discount = now;
        }
    }
}

function showNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body, tag: 'lof-arbitrage', requireInteraction: true });
    }
}

// ========== 风险警告 ==========
function showRiskWarning(code, name) {
    const m = document.createElement('div');
    m.className = 'risk-modal';
    m.innerHTML = `<div class="risk-content"><div class="risk-header"><h3>⚠️ 折价套利风险提示</h3><button class="close-btn" onclick="this.closest('.risk-modal').remove()">×</button></div><div class="risk-body">
        <h4>🎯 ${code} - ${name}</h4>
        <div class="warning-box"><strong>核心风险：赎回价未知</strong><br>实际赎回价格以T+2日净值为准，存在较大不确定性。</div>
        <h4>📊 风险详解：</h4><ul>
            <li><strong>净值波动风险：</strong>T+2日期间净值可能大幅波动</li>
            <li><strong>流动性风险：</strong>场外赎回需3-5个工作日到账</li>
            <li><strong>费用侵蚀：</strong>持有不足7天可能产生1.5%惩罚性赎回费</li>
            <li><strong>折溢价收敛风险：</strong>折价可能在你持有期间收窄甚至变成溢价</li>
        </ul>
        <h4>💡 操作建议：</h4><ul>
            <li>仅适合中长期投资者，短线投机者慎入</li>
            <li>选择规模大、流动性好的基金</li>
            <li>折价率最好大于2%再考虑</li>
            <li>控制单笔仓位，建议不超过总资金的10%</li>
        </ul>
        <div class="warning-box"><strong>⚠️ 重要提醒：</strong><br>历史数据显示折价套利年化收益普遍在5-8%之间，切勿期望过高。</div>
    </div></div>`;
    document.body.appendChild(m);
    m.addEventListener('click', e => { if (e.target === m) m.remove(); });
}

// ========== 自选基金 ==========
function toggleFavorite(code, name, type, nav_date, market_price, nav, rate, profit_after_fee, purchase_status, redeem_status, btn) {
    const idx = favorites.findIndex(f => f.code === code);
    if (idx > -1) {
        favorites.splice(idx, 1);
        btn.innerHTML = '☆'; btn.title = '添加关注';
    } else {
        favorites.push({ code, name, type, nav_date, market_price, nav, rate, profit_after_fee, purchase_status, redeem_status });
        btn.innerHTML = '⭐'; btn.title = '取消关注';
    }
    saveFavorites();
    if (currentTab === 'favorites') renderFavorites();
}

function saveFavorites() {
    localStorage.setItem('lofFavorites', JSON.stringify(favorites));
    document.getElementById('favTab').style.display = favorites.length > 0 ? 'inline-block' : 'none';
}

function loadFavorites() {
    const s = localStorage.getItem('lofFavorites');
    if (s) favorites = JSON.parse(s);
    document.getElementById('favCount').textContent = favorites.length;
    document.getElementById('favTab').style.display = favorites.length > 0 ? 'inline-block' : 'none';
}

function renderFavorites() {
    const tb = document.getElementById('favoritesTableBody');
    document.getElementById('favCount').textContent = favorites.length;
    if (favorites.length === 0) { tb.innerHTML = '<tr><td colspan="10" style="text-align:center;color:#999;">暂无关注的基金</td></tr>'; return; }
    tb.innerHTML = favorites.map(item => {
        const pc = parseFloat(item.profit_after_fee) >= 0 ? 'profit-positive' : 'profit-negative';
        const rate = item.premium_rate !== undefined && item.premium_rate !== '-' ? item.premium_rate : (item.discount_rate || item.rate || '');
        const calcBtn = `<button class="row-calc-btn" onclick="openCalculatorWith('${item.code}','${esc(item.name)}','${item.type||''}','${item.market_price||0}','${item.nav||0}','${rate}','${item.profit_after_fee}','${item.purchase_status||''}','${item.redeem_status||''}')">计算</button>`;
        return `<tr>
            <td><button class="favorite-btn" onclick="removeFavorite('${item.code}','${esc(item.name)}')" title="取消关注">⭐</button> ${item.code}</td>
            <td>${item.name}</td><td>${item.type||'-'}</td><td>${item.nav_date||'-'}</td><td>${item.market_price||'-'}</td><td>${item.nav||'-'}</td>
            <td class="${pc}">${item.rate||'-'}%</td><td class="${pc}">${item.profit_after_fee||'-'}%${calcBtn}</td>
            <td>${getStatusLabel(item.purchase_status)}</td><td>${getStatusLabel(item.redeem_status)}</td>
        </tr>`;
    }).join('');
}

function removeFavorite(code, name) {
    favorites = favorites.filter(f => f.code !== code);
    saveFavorites(); renderFavorites();
}

// ========== 套利收益计算器（增强版）==========
let currentCalcFund = null;

function openCalculator() {
    currentCalcFund = null;
    document.getElementById('calcTitle').textContent = '💰 套利收益计算器';
    document.getElementById('calcFundInfo').style.display = 'none';
    document.getElementById('calcStatusRow').style.display = 'none';
    // 清空字段
    document.getElementById('marketPrice').value = '';
    document.getElementById('navValue').value = '';
    document.getElementById('rateValue').value = '';
    document.getElementById('profitRate').value = '';
    document.getElementById('calcResults').style.display = 'none';
    document.getElementById('calculatorModal').style.display = 'flex';
}

function openCalculatorWith(code, name, type, marketPrice, nav, rate, profitRate, purchaseStatus, redeemStatus) {
    currentCalcFund = { code, name, type, marketPrice, nav, rate, profitRate, purchaseStatus, redeemStatus };

    // 标题显示基金名
    document.getElementById('calcTitle').textContent = '💰 ' + (name || '套利收益计算');
    // 基金信息
    const infoDiv = document.getElementById('calcFundInfo');
    infoDiv.style.display = 'flex';
    document.getElementById('calcFundCode').textContent = code || '-';
    document.getElementById('calcFundName').textContent = name || '-';
    document.getElementById('calcFundType').textContent = type || '';

    // 带入数据
    document.getElementById('marketPrice').value = marketPrice || '';
    document.getElementById('navValue').value = nav || '';
    const rv = parseFloat(rate);
    document.getElementById('rateValue').value = isNaN(rv) ? '' : rv;
    const pv = parseFloat(profitRate);
    document.getElementById('profitRate').value = isNaN(pv) ? '' : pv;

    // 状态提示
    const statusRow = document.getElementById('calcStatusRow');
    const statusHint = document.getElementById('calcStatusHint');
    if (purchaseStatus || redeemStatus) {
        statusRow.style.display = 'flex';
        var hints = [];
        if (purchaseStatus && purchaseStatus !== '正常申购') hints.push('申购:' + purchaseStatus);
        if (redeemStatus && redeemStatus !== '正常赎回') hints.push('赎回:' + redeemStatus);
        statusHint.textContent = hints.length > 0 ? hints.join(' | ') : '状态正常';
        statusHint.className = 'status-hint' + (hints.length > 0 ? ' warn' : '');
    } else {
        statusRow.style.display = 'none';
    }

    document.getElementById('calculatorModal').style.display = 'flex';

    // 有数据就自动计算
    if (marketPrice && nav) calculateProfit();
}

function closeCalculator() { document.getElementById('calculatorModal').style.display = 'none'; }

function calculateProfit() {
    const amount = parseFloat(document.getElementById('investAmount').value) || 10000;
    const mp = parseFloat(document.getElementById('marketPrice').value);
    const nv = parseFloat(document.getElementById('navValue').value);
    const rate = parseFloat(document.getElementById('rateValue').value) || 0;
    const profitRate = parseFloat(document.getElementById('profitRate').value) || 0;

    const rd = document.getElementById('calcResults');
    rd.style.display = 'block';

    if (!mp || !nv || mp <= 0 || nv <= 0) {
        setCalcResult('-', '-', '-', '-', '-');
        document.getElementById('calcDirection').textContent = '请填写价格数据';
        document.getElementById('calcSuggestion').innerHTML = '';
        document.getElementById('calcBreakdown').innerHTML = '';
        document.getElementById('calcWarning').className = 'result-warning';
        return;
    }

    const isPremium = mp > nv;   // 溢价: 场内价 > 净值
    const isDiscount = nv > mp;  // 折价: 净值 > 场内价

    // === 溢价套利计算 ===
    // 方向: 场外申购 → 场内卖出
    let direction, shares, totalFees, expectedProfit, lockDays, feeDetail;

    if (isPremium) {
        direction = '溢价套利：场外申购 → 场内卖出';
        // 申购费用（默认1.5%，四舍五入到0.1%）
        const purchaseFee = 0.015;
        // 实际用于买份额的资金
        const actualInvest = amount / (1 + purchaseFee);
        // 可得份额
        shares = actualInvest / nv;
        // 卖出金额（按场内价格）- 卖出佣金
        const sellCommission = amount * 0.0003; // 万三
        const sellAmount = shares * mp - sellCommission;
        // 预期收益
        expectedProfit = sellAmount - amount;
        totalFees = amount * purchaseFee + sellCommission;
        lockDays = 'T+2 ~ T+3 个工作日';
        feeDetail =
            '<div class="fee-line"><span>申购费 (' + (purchaseFee*100).toFixed(1) + '%)</span><span>' + (amount * purchaseFee).toFixed(2) + ' 元</span></div>' +
            '<div class="fee-line"><span>卖出佣金 (0.03%)</span><span>' + sellCommission.toFixed(2) + ' 元</span></div>';
    }
    // === 折价套利计算 ===
    // 方向: 场内买入 → 场外赎回
    else {
        direction = '折价套利：场内买入 → 场外赎回';
        // 买入份额（含佣金）
        const buyCommission = amount * 0.0003;
        const actualBuy = amount - buyCommission;
        shares = actualBuy / mp;
        // 赎回金额（按净值，假设持有>7天免赎回费）
        const redemptionFee = 0; // >7天通常为0
        const redeemAmount = shares * nv * (1 - redemptionFee);
        expectedProfit = redeemAmount - amount;
        totalFees = buyCommission + redemptionFee * shares * nv;
        lockDays = 'T+3 ~ T+4 个工作日（含确认日）';
        feeDetail =
            '<div class="fee-line"><span>买入佣金 (0.03%)</span><span>' + buyCommission.toFixed(2) + ' 元</span></div>' +
            '<div class="fee-line"><span>赎回费 (>7天)</span><span>0.00 元</span></div>';
    }

    const yieldVal = amount > 0 ? (expectedProfit / amount * 100) : 0;

    // 显示结果
    document.getElementById('calcDirection').textContent = direction;
    document.getElementById('purchaseShares').textContent = shares.toFixed(2) + ' 份';
    document.getElementById('expectedProfit').textContent = (expectedProfit >= 0 ? '+' : '') + expectedProfit.toFixed(2) + ' 元';
    document.getElementById('expectedProfit').className = 'result-value ' + (expectedProfit >= 0 ? 'positive' : 'negative');
    document.getElementById('yieldRate').textContent = (yieldVal >= 0 ? '+' : '') + yieldVal.toFixed(2) + '%';
    document.getElementById('yieldRate').className = 'result-value ' + (yieldVal >= 0 ? 'positive' : 'negative');
    document.getElementById('totalFees').textContent = totalFees.toFixed(2) + ' 元';
    document.getElementById('fundLockDays').textContent = lockDays;

    // 费用明细
    document.getElementById('calcBreakdown').innerHTML = '<h5>📋 费用拆解（投资 ' + amount.toLocaleString() + ' 元）</h5><div class="fee-list">' + feeDetail + '</div>';

    // 操作建议
    var suggestionHtml = '';
    if (isPremium) {
        suggestionHtml = '<h5>💡 操作步骤（溢价套利）</h5>' +
            '<ol class="suggestion-steps">' +
            '<li>在场外平台（支付宝/天天基金等）以净值 <strong>' + nv.toFixed(4) + '</strong> 申购该基金</li>' +
            '<li>等待 <strong>T+2</strong> 日份额到账</li>' +
            '<li>在证券账户中以市价 <strong>' + mp.toFixed(4) + '</strong> 卖出</li>' +
            '</ol>';
    } else {
        suggestionHtml = '<h5>💡 操作步骤（折价套利）</h5>' +
            '<ol class="suggestion-steps">' +
            '<li>在证券账户中以市价 <strong>' + mp.toFixed(4) + '</strong> 买入</li>' +
            '<li>等待 <strong>T+1</strong> 日份额到账</li>' +
            '<li>在场外平台发起赎回，按净值 <strong>' + nv.toFixed(4) + '</strong> 结算</li>' +
            '<li>注意：赎回价以提交申请后首个交易日的净值为准！</li>' +
            '</ol>';
    }
    document.getElementById('calcSuggestion').innerHTML = suggestionHtml;

    // 风险提示
    const warn = document.getElementById('calcWarning');
    var warns = [];
    if (Math.abs(yieldVal) < 0.5) {
        warns.push('<strong>收益较低</strong>：扣费后收益率不足 0.5%，交易费用可能侵蚀利润。');
    } else if (Math.abs(yieldVal) > 5) {
        warns.push('<strong>高收益高风险</strong>：收益率超过 5%，但溢价/折价可能快速收敛，注意控制仓位！');
    }

    // 状态相关风险
    if (currentCalcFund) {
        var ps = currentCalcFund.purchaseStatus;
        var rs = currentCalcFund.redeem_status;
        if (ps && ps.indexOf('暂停') >= 0) {
            warns.push('<strong>暂停申购</strong>：当前无法申购，需等待开放后操作，期间净值可能变化。');
        }
        if (rs && rs.indexOf('暂停') >= 0) {
            warns.push('<strong>暂停赎回</strong>：当前无法赎回，折价套利暂时不可行。');
        }
    }

    if (warns.length > 0) {
        warn.innerHTML = '⚠️ ' + warns.join('<br>⚠️ ');
        warn.className = 'result-warning show';
    } else {
        warn.className = 'result-warning';
    }
}

// 点击背景关闭计算器
document.addEventListener('click', function(e) {
    if (e.target.id === 'calculatorModal') closeCalculator();
});

// ========== 个人信息面板 ==========
function openProfile() {
    document.getElementById('profileModal').style.display = 'flex';
    loadProfileData();
}

function closeProfile() {
    document.getElementById('profileModal').style.display = 'none';
    cancelEdit();
}

async function loadProfileData() {
    try {
        const res = await fetch('/api/user/profile');
        const data = await res.json();
        if (data.success && data.data) {
            const u = data.data;
            document.getElementById('profileAvatar').textContent = (u.nickname || u.username || '?').charAt(0).toUpperCase();
            document.getElementById('profileUsername').textContent = u.username || '-';
            document.getElementById('profileNickname').textContent = u.nickname || '未设置';
            document.getElementById('profileEmail').textContent = u.email || '未设置';
            const roleEl = document.getElementById('profileRole');
            roleEl.textContent = (u.role || 'free') === 'admin' ? '管理员' : (u.role === 'vip' ? 'VIP用户' : '普通用户');
            roleEl.className = 'role-' + (u.role || 'free');
            // Fill edit form
            document.getElementById('editNickname').value = u.nickname || '';
            document.getElementById('editEmail').value = u.email || '';
        }
    } catch (e) {
        console.error('加载个人资料失败:', e);
    }
}

function showEditProfile() {
    document.getElementById('profileView').style.display = 'none';
    document.getElementById('profileEdit').style.display = 'block';
}

function cancelEdit() {
    document.getElementById('profileEdit').style.display = 'none';
    document.getElementById('profileView').style.display = 'block';
}

async function saveProfile() {
    const nickname = document.getElementById('editNickname').value.trim();
    const email = document.getElementById('editEmail').value.trim();
    try {
        const res = await fetch('/api/user/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nickname, email })
        });
        const data = await res.json();
        if (data.success) {
            showNotification('保存成功', '资料已更新');
            // Refresh local user info
            currentUser.nickname = nickname;
            currentUser.email = email;
            updateUserUI(true);
            cancelEdit();
            loadProfileData();
        } else {
            alert(data.error || '保存失败');
        }
    } catch (e) {
        console.error('保存失败:', e);
        alert('网络错误，请重试');
    }
}

// 点击背景关闭
document.addEventListener('click', function(e) {
    if (e.target.id === 'profileModal') closeProfile();
});

// ========== 暗色模式 ==========
function toggleTheme() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('lofTheme', isDark ? 'dark' : 'light');
    document.getElementById('themeBtn').textContent = isDark ? '☀️' : '🌙';
}

function loadTheme() {
    const t = localStorage.getItem('lofTheme');
    if (t === 'dark') {
        document.body.classList.add('dark-mode');
        document.getElementById('themeBtn').textContent = '☀️';
    }
}

// ========== Enter键搜索 ==========
document.addEventListener('DOMContentLoaded', function() {
    ['premiumSearch','discountSearch','qdiiSearch','searchInput'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                if (id === 'searchInput') searchFund();
                else applyFilter(id.replace('Search',''));
            }
        });
    });
});

// ==========================================
// ========== 基金详情抽屉 (v5.1) ===========
// ==========================================

let fdCurrentFund = null;   // 当前详情基金数据
let fdNavChart = null;      // Chart.js 实例
let fdAllNavData = [];      // 全量历史净值（用于切换周期）
let fdNavTotalCount = 0;    // 净值总条数
let fdNavPageCount = 0;     // 当前已显示条数
let fdCurrentPeriod = '1m'; // 当前周期

/**
 * 打开基金详情抽屉
 * @param {string} code  基金代码
 * @param {object} rowData 来自表格的已有数据（可选，用于快速填充）
 */
function openFundDetail(code, rowData) {
    if (!code) return;
    fdCurrentFund = rowData || { code };

    // 打开抽屉
    document.getElementById('fundDetailOverlay').classList.add('open');
    document.getElementById('fundDetailDrawer').classList.add('open');
    document.body.style.overflow = 'hidden';

    // 重置内容
    _fdReset(code);

    // 填充已知数据（来自表格）
    if (rowData) {
        document.getElementById('fdCode').textContent = code;
        document.getElementById('fdName').textContent = rowData.name || code;
        document.getElementById('fdType').textContent = rowData.type || '-';
        document.getElementById('fdNavDate').textContent = rowData.nav_date || '-';
        document.getElementById('fdMarketPrice').textContent = rowData.market_price || '-';
        document.getElementById('fdNav').textContent = rowData.nav || '-';

        const premRate = parseFloat(rowData.premium_rate);
        const discRate = parseFloat(rowData.discount_rate);
        const rateVal = !isNaN(premRate) && premRate !== 0 ? premRate : (!isNaN(discRate) ? discRate : null);
        if (rateVal !== null) {
            const rateEl = document.getElementById('fdPremiumRate');
            rateEl.textContent = (rateVal > 0 ? '+' : '') + rateVal.toFixed(2) + '%';
            rateEl.style.color = rateVal > 0 ? '#f44336' : '#4caf50';
        }

        const profitVal = parseFloat(rowData.profit_after_fee);
        if (!isNaN(profitVal)) {
            const profEl = document.getElementById('fdProfit');
            profEl.textContent = (profitVal > 0 ? '+' : '') + profitVal.toFixed(2) + '%';
            profEl.style.color = profitVal > 0 ? '#f44336' : '#4caf50';
        }

        // 申购/赎回状态（附基金公告链接：暂停/恢复申购的原始出处）
        const ggUrl = `https://fundf10.eastmoney.com/jjgg_${code}.html`;
        document.getElementById('fdStatus').innerHTML =
            (rowData.purchase_status || '-') + ' / ' + (rowData.redeem_status || '-') +
            `<a class="fd-gg-link" href="${ggUrl}" target="_blank" rel="noopener" title="查看基金公告（暂停/恢复申购原始出处）">公告↗</a>`;

        // 自选按钮状态
        const isFav = favorites.some(f => f.code === code);
        const favBtn = document.getElementById('fdFavBtn');
        favBtn.textContent = isFav ? '⭐ 已自选' : '☆ 自选';
        favBtn.className = 'fd-fav-btn' + (isFav ? ' active' : '');
    }

    // 异步拉取更多信息（统一通过后端代理，避免 CORS）
    _fdFetchAllDetail(code);
}

/** 关闭抽屉 */
function closeFundDetail() {
    document.getElementById('fundDetailOverlay').classList.remove('open');
    document.getElementById('fundDetailDrawer').classList.remove('open');
    document.body.style.overflow = '';
}

/** 重置抽屉内容 */
function _fdReset(code) {
    document.getElementById('fdCode').textContent = code;
    document.getElementById('fdName').textContent = '加载中...';
    ['fdType','fdSetupDate','fdScale','fdCompany','fdManager','fdIndex'].forEach(id => {
        document.getElementById(id).textContent = '-';
    });
    ['fdMarketPrice','fdNav','fdPremiumRate','fdProfit','fdNavDate','fdStatus'].forEach(id => {
        const el = document.getElementById(id);
        el.textContent = '-';
        el.style.color = '';
    });
    ['fdPerf1w','fdPerf1m','fdPerf3m','fdPerf6m','fdPerf1y','fdPerfAll'].forEach(id => {
        const el = document.getElementById(id);
        el.textContent = '-';
        el.className = 'fd-perf-value';
    });
    document.getElementById('fdNavTableBody').innerHTML =
        '<tr><td colspan="4" style="text-align:center;color:#999;">加载中...</td></tr>';
    document.getElementById('fdChartLoading').classList.remove('hidden');
    fdAllNavData = [];
    fdNavTotalCount = 0;
    fdNavPageCount = 0;
    fdCurrentPeriod = 'ytd';
    // 重置图表周期按钮（默认"今年"为active）
    document.querySelectorAll('.fd-chart-tab').forEach((btn, i) => {
        btn.classList.toggle('active', btn.textContent === '今年');
    });
    // 销毁旧 Chart
    if (fdNavChart) { fdNavChart.destroy(); fdNavChart = null; }
}

/** 通过后端代理获取基金详情（基本信息 + 业绩 + 基金经理），避免 CORS */
async function _fdFetchAllDetail(code) {
    try {
        const res = await fetch(`/api/fund/detail?code=${encodeURIComponent(code)}`);
        const json = await res.json();
        if (!json.success || !json.data) return;
        const data = json.data;

        // --- 基本信息 ---
        const basic = data.basic || {};
        if (basic.name) document.getElementById('fdName').textContent = basic.name;
        if (basic.type) document.getElementById('fdType').textContent = basic.type;
        if (basic.setup_date) document.getElementById('fdSetupDate').textContent = basic.setup_date;
        if (basic.scale && basic.scale !== '--') {
            const sv = parseFloat(basic.scale);
            document.getElementById('fdScale').textContent = isNaN(sv) ? basic.scale : _fdFormatScale(sv);
        }
        if (basic.company && basic.company !== '--') document.getElementById('fdCompany').textContent = basic.company;
        if (basic.index_name && basic.index_name !== '--') {
            document.getElementById('fdIndex').textContent = basic.index_name;
        } else if (basic.cycle) {
            document.getElementById('fdIndex').textContent = '封闭期: ' + basic.cycle;
        }

        // --- 基金经理 ---
        if (data.manager) document.getElementById('fdManager').textContent = data.manager;

        // --- 业绩数据 ---
        const perf = data.performance || {};
        const perfMap = { '1w': 'fdPerf1w', '1m': 'fdPerf1m', '3m': 'fdPerf3m', '6m': 'fdPerf6m', '1y': 'fdPerf1y', '3y': 'fdPerf3y', 'all': 'fdPerfAll' };
        for (const [key, elId] of Object.entries(perfMap)) {
            const el = document.getElementById(elId);
            if (!el) continue;
            const val = perf[key];
            if (val === undefined || val === null || val === '') {
                el.textContent = '-'; el.className = 'fd-perf-value flat';
            } else {
                const v = parseFloat(val);
                el.textContent = (v > 0 ? '+' : '') + v.toFixed(2) + '%';
                el.className = 'fd-perf-value ' + (v > 0 ? 'pos' : v < 0 ? 'neg' : 'flat');
            }
        }
    } catch (e) {
        console.warn('[基金详情] 详情加载失败:', e);
    }

    // 加载历史净值（通过后端代理，全量加载）
    _fdFetchNavHistory(code);
}

/** 全量加载历史净值并渲染图表 + 表格（后端 pingzhongdata 代理，一次返回全部数据） */
async function _fdFetchNavHistory(code) {
    document.getElementById('fdChartLoading').classList.remove('hidden');
    document.getElementById('fdNavTableBody').innerHTML =
        '<tr><td colspan="4" style="text-align:center;color:#999;">加载中...</td></tr>';
    try {
        const url = `/api/fund/nav_history?code=${encodeURIComponent(code)}`;
        const res = await fetch(url);
        if (!res.ok) {
            const errText = await res.text().catch(() => '');
            throw new Error(`HTTP ${res.status}: ${errText}`);
        }
        const json = await res.json();
        if (!json.success || !json.data) {
            throw new Error(json.error || '接口返回异常');
        }

        const list = json.data.LSJZList || [];
        if (!list.length) {
            document.getElementById('fdNavTableBody').innerHTML =
                '<tr><td colspan="4" style="text-align:center;color:#999;">暂无净值数据</td></tr>';
            document.getElementById('fdChartLoading').classList.add('hidden');
            return;
        }

        // 存储全量数据（后端已按最新在前排列）
        fdAllNavData = list;
        fdNavTotalCount = json.totalCount || list.length;

        // 渲染历史净值表（分页，初始显示20条）
        fdNavPageCount = 0;
        _fdRenderNavTable();

        // 绘图（使用当前选中的周期，默认今年）
        _fdDrawChart(fdCurrentPeriod);

        // 更新表格标题显示总条数
        const navTitleEl = document.getElementById('fdNavTitle');
        if (navTitleEl) {
            navTitleEl.innerHTML = '📅 历史净值 <span style="font-weight:400;font-size:12px;color:#999;">共 ' + fdNavTotalCount + ' 条</span>';
        }

    } catch (e) {
        console.error('[基金详情] 历史净值加载失败:', e);
        const errMsg = e && e.message ? e.message : '未知错误';
        document.getElementById('fdNavTableBody').innerHTML =
            `<tr><td colspan="4" style="text-align:center;color:#f44336;padding:16px 0;">
                <div>净值数据加载失败</div>
                <div style="font-size:12px;color:#999;margin-top:4px;">${errMsg}</div>
            </td></tr>`;
        document.getElementById('fdChartLoading').classList.add('hidden');
    }
}

/** 渲染历史净值表格（分页加载，每次追加20条） */
function _fdRenderNavTable() {
    const pageSize = 20;
    const start = fdNavPageCount;
    const end = Math.min(start + pageSize, fdAllNavData.length);
    const newItems = fdAllNavData.slice(start, end);

    if (start === 0) {
        // 首次渲染
        const rows = newItems.map(row => _fdBuildNavRow(row)).join('');
        document.getElementById('fdNavTableBody').innerHTML = rows || '<tr><td colspan="4" style="text-align:center;color:#999;">暂无净值数据</td></tr>';
    } else {
        // 追加渲染
        const tbody = document.getElementById('fdNavTableBody');
        // 移除旧的"加载更多"行
        const loadMoreRow = tbody.querySelector('.fd-load-more-row');
        if (loadMoreRow) loadMoreRow.remove();
        tbody.insertAdjacentHTML('beforeend', newItems.map(row => _fdBuildNavRow(row)).join(''));
    }
    fdNavPageCount = end;

    // 判断是否需要"加载更多"按钮
    _fdUpdateLoadMoreBtn();
}

/** 构建单行历史净值表格HTML */
function _fdBuildNavRow(row) {
    const dv = parseFloat(row.JZZZL);
    const dvClass = isNaN(dv) ? '' : (dv > 0 ? 'style="color:#f44336;font-weight:600"' : dv < 0 ? 'style="color:#4caf50;font-weight:600"' : '');
    const dvText = isNaN(dv) ? '-' : (dv > 0 ? '+' : '') + dv.toFixed(2) + '%';
    return `<tr>
        <td>${row.FSRQ || '-'}</td>
        <td>${row.DWJZ || '-'}</td>
        <td>${row.LJJZ || '-'}</td>
        <td ${dvClass}>${dvText}</td>
    </tr>`;
}

/** 更新"加载更多"按钮状态 */
function _fdUpdateLoadMoreBtn() {
    const tbody = document.getElementById('fdNavTableBody');
    // 移除旧按钮
    const old = tbody.querySelector('.fd-load-more-row');
    if (old) old.remove();

    if (fdNavPageCount < fdAllNavData.length) {
        const remaining = fdAllNavData.length - fdNavPageCount;
        const showCount = Math.min(20, remaining);
        const tr = document.createElement('tr');
        tr.className = 'fd-load-more-row';
        tr.innerHTML = `<td colspan="4" style="text-align:center;padding:8px;">
            <button class="fd-load-more-btn" onclick="_fdLoadMoreNav()">
                加载更多（还有 ${remaining} 条，本次加载 ${showCount} 条）
            </button>
        </td>`;
        tbody.appendChild(tr);
    }
}

/** 加载更多历史净值 */
function _fdLoadMoreNav() {
    _fdRenderNavTable();
}

/** 根据周期切换图表数据 */
function switchChartPeriod(period, btn) {
    fdCurrentPeriod = period;
    document.querySelectorAll('.fd-chart-tab').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    _fdDrawChart(period);
}

/** 绘制净值折线图（支持累计净值双线） */
function _fdDrawChart(period) {
    if (!fdAllNavData.length) return;
    if (typeof Chart === 'undefined') {
        console.error('[NAV] Chart.js 未加载，无法绘制图表');
        document.getElementById('fdChartLoading').classList.add('hidden');
        return;
    }
    document.getElementById('fdChartLoading').classList.add('hidden');

    // 数据需要倒序（最早的在前）用于图表
    const allDataReversed = [...fdAllNavData].reverse();

    // 根据周期过滤数据
    const now = new Date();
    let filtered;
    if (period === 'ytd') {
        // 今年：从1月1日起
        const yearStart = new Date(now.getFullYear(), 0, 1);
        filtered = allDataReversed.filter(row => {
            if (!row.FSRQ) return false;
            return new Date(row.FSRQ) >= yearStart;
        });
    } else {
        const cutoffs = { '1m': 30, '3m': 90, '6m': 180, '1y': 365, 'all': 99999 };
        const days = cutoffs[period] || 30;
        const cutDate = new Date(now - days * 86400000);
        filtered = allDataReversed.filter(row => {
            if (!row.FSRQ) return false;
            return new Date(row.FSRQ) >= cutDate;
        });
    }
    if (filtered.length === 0) filtered = allDataReversed;

    const labels = filtered.map(r => r.FSRQ);
    const navValues = filtered.map(r => parseFloat(r.DWJZ) || null);
    const accNavValues = filtered.map(r => parseFloat(r.LJJZ) || null);

    // 计算统计摘要
    const validNav = navValues.filter(v => v !== null);
    const stats = {
        maxNav: validNav.length ? Math.max(...validNav) : null,
        minNav: validNav.length ? Math.min(...validNav) : null,
        latestNav: validNav.length ? validNav[validNav.length - 1] : null,
        firstNav: validNav.length ? validNav[0] : null,
    };
    if (stats.firstNav && stats.latestNav) {
        stats.totalReturn = ((stats.latestNav - stats.firstNav) / stats.firstNav * 100);
    }
    // 更新统计摘要显示
    _fdUpdateChartStats(stats, period);

    const canvas = document.getElementById('fdNavChart');
    const isDark = document.body.classList.contains('dark-mode');
    const textColor = isDark ? '#aaa' : '#666';
    const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

    if (fdNavChart) { fdNavChart.destroy(); fdNavChart = null; }

    const datasets = [
        {
            label: '单位净值',
            data: navValues,
            borderColor: '#667eea',
            backgroundColor: 'rgba(102,126,234,0.08)',
            borderWidth: 2,
            pointRadius: filtered.length > 60 ? 0 : 2,
            pointHoverRadius: 5,
            fill: true,
            tension: 0.3,
        }
    ];

    // 累计净值线（仅当 LJJZ 与 DWJZ 有明显差异时才绘制）
    const hasValidAccNav = accNavValues.some((v, i) =>
        v !== null && v > 0 && Math.abs(v - (navValues[i] || 0)) > 0.001
    );
    if (hasValidAccNav) {
        datasets.push({
            label: '累计净值',
            data: accNavValues,
            borderColor: '#f0937b',
            backgroundColor: 'rgba(240,147,123,0.05)',
            borderWidth: 1.5,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderDash: [4, 2],
            fill: false,
            tension: 0.3,
        });
    }

    fdNavChart = new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: {
                    display: hasValidAccNav,
                    position: 'top',
                    labels: {
                        color: textColor,
                        font: { size: 11 },
                        boxWidth: 16,
                        boxHeight: 2,
                        padding: 12,
                    }
                },
                tooltip: {
                    backgroundColor: isDark ? 'rgba(30,30,46,0.95)' : 'rgba(255,255,255,0.96)',
                    titleColor: isDark ? '#ddd' : '#333',
                    bodyColor: isDark ? '#bbb' : '#555',
                    borderColor: isDark ? '#333' : '#eee',
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 6,
                    titleFont: { size: 12, weight: '600' },
                    bodyFont: { size: 12 },
                    callbacks: {
                        label: ctx => {
                            const val = ctx.parsed.y;
                            if (val === null) return ctx.dataset.label + ': -';
                            return ctx.dataset.label + ': ' + val.toFixed(4);
                        },
                        afterBody: items => {
                            // 如果有两条线，计算差值
                            if (items.length >= 2 && items[0].parsed.y !== null && items[1].parsed.y !== null) {
                                const diff = items[0].parsed.y - items[1].parsed.y;
                                return ['', '差额: ' + (diff >= 0 ? '+' : '') + diff.toFixed(4)];
                            }
                            return [];
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: textColor,
                        maxTicksLimit: 8,
                        maxRotation: 0,
                        font: { size: 11 }
                    },
                    grid: { color: gridColor }
                },
                y: {
                    ticks: {
                        color: textColor,
                        font: { size: 11 },
                        callback: v => v.toFixed(3)
                    },
                    grid: { color: gridColor }
                }
            }
        }
    });
}

/** 更新图表下方的统计摘要 */
function _fdUpdateChartStats(stats, period) {
    const el = document.getElementById('fdChartStats');
    if (!el) return;
    if (!stats.latestNav) {
        el.innerHTML = '';
        return;
    }
    const periodLabels = { '1m': '近1月', '3m': '近3月', '6m': '近6月', '1y': '近1年', 'ytd': '今年', 'all': '成立以来' };
    const periodLabel = periodLabels[period] || '';

    let html = `<div class="fd-chart-stats">
        <div class="fd-stat-item">
            <span class="fd-stat-label">区间最高</span>
            <span class="fd-stat-value" style="color:#f44336;">${stats.maxNav !== null ? stats.maxNav.toFixed(4) : '-'}</span>
        </div>
        <div class="fd-stat-item">
            <span class="fd-stat-label">区间最低</span>
            <span class="fd-stat-value" style="color:#4caf50;">${stats.minNav !== null ? stats.minNav.toFixed(4) : '-'}</span>
        </div>
        <div class="fd-stat-item">
            <span class="fd-stat-label">${periodLabel}涨幅</span>
            <span class="fd-stat-value" style="color:${stats.totalReturn >= 0 ? '#f44336' : '#4caf50'};">${stats.totalReturn !== undefined ? (stats.totalReturn >= 0 ? '+' : '') + stats.totalReturn.toFixed(2) + '%' : '-'}</span>
        </div>
        <div class="fd-stat-item">
            <span class="fd-stat-label">最新净值</span>
            <span class="fd-stat-value">${stats.latestNav.toFixed(4)}</span>
        </div>
    </div>`;
    el.innerHTML = html;
}

/** 从详情页打开计算器 */
function openCalcFromDetail() {
    if (!fdCurrentFund) return;
    const d = fdCurrentFund;
    const rate = (d.premium_rate !== undefined && d.premium_rate !== '-') ? d.premium_rate : (d.discount_rate || '');
    openCalculatorWith(d.code, d.name, d.type, d.market_price, d.nav, rate, d.profit_after_fee, d.purchase_status, d.redeem_status);
}

/** 从详情页切换自选 */
function toggleFavFromDetail() {
    if (!fdCurrentFund) return;
    const d = fdCurrentFund;
    const code = d.code;
    const idx = favorites.findIndex(f => f.code === code);
    if (idx > -1) {
        favorites.splice(idx, 1);
    } else {
        const rate = (d.premium_rate !== '-' && d.premium_rate !== undefined) ? d.premium_rate : (d.discount_rate || '');
        favorites.push({
            code, name: d.name, type: d.type, nav_date: d.nav_date,
            market_price: d.market_price, nav: d.nav, rate,
            profit_after_fee: d.profit_after_fee,
            purchase_status: d.purchase_status, redeem_status: d.redeem_status
        });
    }
    saveFavorites();
    // 同步更新抽屉按钮
    const isFav = favorites.some(f => f.code === code);
    const favBtn = document.getElementById('fdFavBtn');
    favBtn.textContent = isFav ? '⭐ 已自选' : '☆ 自选';
    favBtn.className = 'fd-fav-btn' + (isFav ? ' active' : '');
    // 同步更新表格里的星星
    document.querySelectorAll('.favorite-btn').forEach(btn => {
        const onclick = btn.getAttribute('onclick') || '';
        if (onclick.includes(`'${code}'`)) {
            btn.innerHTML = isFav ? '⭐' : '☆';
            btn.title = isFav ? '取消关注' : '添加关注';
        }
    });
    if (currentTab === 'favorites') renderFavorites();
}

/** 格式化基金规模 */
function _fdFormatScale(v) {
    if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿元';
    if (v >= 1e4) return (v / 1e4).toFixed(2) + ' 万元';
    return v.toFixed(2) + ' 元';
}

// ==========================================
// 将表格中基金代码改为可点击
// 覆盖 renderTable，在渲染时给代码加点击事件
// ==========================================
const _origRenderTable = renderTable;
renderTable = function(type) {
    _origRenderTable(type);
    // 给表格 tbody 里的基金名称列加上点击事件
    const tbody = document.getElementById(`${type}TableBody`);
    if (!tbody) return;
    tbody.querySelectorAll('tr').forEach(tr => {
        const tds = tr.querySelectorAll('td');
        if (tds.length < 2) return;
        // 第0列是"⭐ CODE"，从文本里提取6位数字代码
        const codeCell = tds[0];
        const codeText = codeCell.textContent.replace(/[^\d]/g, '');
        if (!codeText || codeText.length < 6) return;
        const code = codeText.substring(0, 6);

        // 给基金名称列 (td[1]) 添加可点击样式
        const nameCell = tds[1];
        const name = nameCell.textContent.trim();
        if (name && name !== '-') {
            const span = document.createElement('span');
            span.className = 'fund-code-link';
            span.dataset.code = code;
            span.dataset.type = type;
            span.textContent = name;
            span.onclick = function() {
                const data = currentData[type];
                const rowData = data ? data.find(d => d.code === this.dataset.code) : null;
                openFundDetail(this.dataset.code, rowData || { code: this.dataset.code, name: this.textContent });
            };
            nameCell.innerHTML = '';
            nameCell.appendChild(span);
        }
    });
};

// ==========================================
// 同样覆盖 renderFavorites：自选表格的基金名称也可点击打开详情
// （renderFavorites 不走 renderTable，需要单独绑定）
// ==========================================
const _origRenderFavorites = renderFavorites;
renderFavorites = function() {
    _origRenderFavorites();
    const tbody = document.getElementById('favoritesTableBody');
    if (!tbody) return;
    tbody.querySelectorAll('tr').forEach(tr => {
        const tds = tr.querySelectorAll('td');
        if (tds.length < 2) return;
        // 第0列是"⭐ CODE"，提取6位数字代码
        const codeText = tds[0].textContent.replace(/[^\d]/g, '');
        if (!codeText || codeText.length < 6) return;
        const code = codeText.substring(0, 6);

        const nameCell = tds[1];
        const name = nameCell.textContent.trim();
        if (name && name !== '-') {
            const span = document.createElement('span');
            span.className = 'fund-code-link';
            span.dataset.code = code;
            span.textContent = name;
            span.onclick = function() {
                const rd = favorites.find(f => f.code === code);
                // 自选数据可能只有合成 rate 字段，映射为 premium_rate 供详情弹窗展示
                const rowData = rd
                    ? { ...rd, premium_rate: (rd.premium_rate !== undefined && rd.premium_rate !== '-') ? rd.premium_rate : (rd.rate || '-') }
                    : { code, name };
                openFundDetail(code, rowData);
            };
            nameCell.innerHTML = '';
            nameCell.appendChild(span);
        }
    });
};

// 同样覆盖 searchFund 里搜索结果的点击
document.addEventListener('click', function(e) {
    // 搜索结果 result-card 的基金代码点击
    if (e.target.classList.contains('fd-open-detail')) {
        const code = e.target.dataset.code;
        const name = e.target.dataset.name;
        if (code) openFundDetail(code, { code, name });
    }
});