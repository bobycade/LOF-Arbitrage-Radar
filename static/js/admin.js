/* ============================================
   LOF套利雷达 - 管理后台交互逻辑 v5.0
   ============================================ */

// --- 侧边栏折叠 ---
function toggleSidebar() {
    const sidebar = document.getElementById('adminSidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

// 点击侧边栏外部关闭(移动端)
document.addEventListener('click', function(e) {
    const sidebar = document.getElementById('adminSidebar');
    const toggle = document.querySelector('.sidebar-toggle');
    if (sidebar && sidebar.classList.contains('open')) {
        if (!sidebar.contains(e.target) && !toggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    }
});

// --- Toast 通知 ---
function showToast(message, type) {
    type = type || 'success';
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = message;
    toast.className = `admin-toast show toast-${type}`;
    
    setTimeout(function() {
        toast.className = 'admin-toast';
    }, 2500);
}

// --- API请求封装 ---
function apiPost(url, data) {
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data || {})
    }).then(function(r) { return r.json(); });
}

// --- 页面加载完成 ---
document.addEventListener('DOMContentLoaded', function() {
    // 自动隐藏URL中的成功/错误消息参数
});
