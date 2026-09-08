/** 认证检查 —— 没有 token 跳转到 /login */
(function() {
  if (window.location.pathname === '/login') return;

  const token = localStorage.getItem('access_token');
  if (!token) {
    window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname + window.location.search);
    return;
  }

  // 验证 token 是否过期
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      localStorage.clear();
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname + window.location.search);
      return;
    }
  } catch(e) {}

  // 显示当前用户
  window.currentUser = {
    username: localStorage.getItem('username'),
    displayName: localStorage.getItem('display_name'),
    role: localStorage.getItem('role')
  };

  // 标记 body，让 CSS 根据角色显隐元素
  document.body.setAttribute('data-role', window.currentUser.role);
  document.body.setAttribute('data-logged-in', 'true');
})();

function logout() {
  localStorage.clear();
  window.location.href = '/login';
}

// 管理员专属：显示系统管理菜单
(function() {
  if (window.currentUser && window.currentUser.role === 'admin') {
    var adminNav = document.getElementById('nav-section-admin');
    if (adminNav) adminNav.style.display = '';
  }
})();
