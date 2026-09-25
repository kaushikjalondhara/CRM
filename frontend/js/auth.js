/**
 * CRM Authentication & Authorization Module
 * Handles login, logout, session persistence, role and permission checks,
 * and page-level route guards.
 */

const Auth = (() => {
  const USER_KEY = 'crm_user_profile';

  /**
   * Check whether an active token exists
   */
  function isAuthenticated() {
    return Boolean(ApiClient.getToken());
  }

  /**
   * Get cached user profile from client storage
   */
  /**
   * Get cached user profile from client storage (checks sessionStorage first, then localStorage)
   */
  function getUser() {
    try {
      const stored = sessionStorage.getItem(USER_KEY) || localStorage.getItem(USER_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch (e) {
      return null;
    }
  }

  /**
   * Save user profile in client storage
   */
  function setUser(user, remember = false) {
    if (!user) return;
    const json = JSON.stringify(user);
    if (remember) {
      localStorage.setItem(USER_KEY, json);
      sessionStorage.setItem(USER_KEY, json);
    } else {
      sessionStorage.setItem(USER_KEY, json);
      localStorage.removeItem(USER_KEY);
    }
  }

  /**
   * Clear user profile from storage
   */
  function clearUser() {
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(USER_KEY);
    localStorage.removeItem('crm_auth_token');
    sessionStorage.removeItem('crm_auth_token');
  }

  /**
   * Perform backend login request and store session upon success
   */
  async function login(email, password, remember = false) {
    const res = await ApiClient.post('/api/auth/login', { email, password });

    const responsePayload = res.data || {};
    const token = responsePayload.token || (responsePayload.data && responsePayload.data.token);

    if (!res.success || !token) {
      return {
        success: false,
        message: res.error || responsePayload.message || 'Authentication failed'
      };
    }

    // Save token using ApiClient
    ApiClient.setToken(token, remember);

    // Fetch full profile including database permissions
    const meRes = await fetchCurrentUser();
    const fullUser = (meRes && meRes.user) ? meRes.user : (responsePayload.user || (responsePayload.data && responsePayload.data.user));
    setUser(fullUser, remember);

    return {
      success: true,
      user: fullUser
    };
  }

  /**
   * Perform backend logout, clear client tokens, and redirect to login page
   */
  async function logout() {
    try {
      await ApiClient.post('/api/auth/logout');
    } catch (e) {
      // Ignore network errors during logout
    } finally {
      ApiClient.clearToken();
      clearUser();
      window.location.href = 'login.html';
    }
  }

  /**
   * Fetch live authenticated user profile from GET /api/auth/me
   */
  async function fetchCurrentUser() {
    if (!isAuthenticated()) return null;

    const res = await ApiClient.get('/api/auth/me');
    if (res.success && res.data && res.data.user) {
      const isRemember = Boolean(localStorage.getItem('crm_remember_session'));
      setUser(res.data.user, isRemember);
      return res.data;
    }

    // If fetch fails with 401, clear credentials
    if (res.status === 401) {
      ApiClient.clearToken();
      clearUser();
    }
    return null;
  }

  /**
   * Check if current user has a specific permission
   */
  function hasPermission(permissionName) {
    const user = getUser();
    if (!user) return false;
    if (user.role === 'Admin') return true;
    return Array.isArray(user.permissions) && user.permissions.includes(permissionName);
  }

  /**
   * Check if current user has a specific role
   */
  function hasRole(roleName) {
    const user = getUser();
    return Boolean(user && user.role === roleName);
  }

  /**
   * Protected Route Guard: Call on protected pages (like dashboard.html)
   * If unauthenticated, immediately redirects to login.html
   */
  /**
   * Protected Route Guard: Call on protected pages (like dashboard.html)
   * If unauthenticated, immediately redirects to login.html.
   * If unauthorized for current route, redirects to dashboard.html.
   */
  async function requireAuth() {
    if (!isAuthenticated()) {
      window.location.href = 'login.html';
      return null;
    }

    // Validate token with live backend profile
    const profile = await fetchCurrentUser();
    if (!profile || !profile.user) {
      window.location.href = 'login.html?session=expired';
      return null;
    }

    const user = profile.user;

    // Populate dashboard user indicators & filter sidebar by user role permissions
    applyUserToDashboard(user);
    applyPermissionVisibility(user);

    // Page-level access guard based on URL filename
    const currentPage = window.location.pathname.split('/').pop().split('?')[0];
    const roleAllowedPages = {
      'Admin': null, // All pages allowed
      'Manager': ['dashboard.html', 'customers.html', 'leads.html', 'deals.html', 'tasks.html', 'calls.html', 'meetings.html', 'calendar.html', 'products.html', 'invoices.html', 'payments.html', 'emails.html', 'notifications.html', 'reports.html', 'users.html', 'settings.html', 'profile.html'],
      'Sales Employee': ['dashboard.html', 'customers.html', 'leads.html', 'deals.html', 'tasks.html', 'calls.html', 'meetings.html', 'calendar.html', 'emails.html', 'notifications.html', 'profile.html'],
      'Sales': ['dashboard.html', 'customers.html', 'leads.html', 'deals.html', 'tasks.html', 'calls.html', 'meetings.html', 'calendar.html', 'emails.html', 'notifications.html', 'profile.html'],
      'Staff': ['dashboard.html', 'customers.html', 'tasks.html', 'calls.html', 'meetings.html', 'products.html', 'notifications.html', 'profile.html']
    };

    if (user.role !== 'Admin') {
      const allowedList = roleAllowedPages[user.role];
      if (allowedList && !allowedList.includes(currentPage) && currentPage !== 'dashboard.html' && currentPage !== 'notifications.html' && currentPage !== 'profile.html') {
        window.location.href = 'dashboard.html?error=unauthorized';
        return null;
      }
    }

    return user;
  }

  /**
   * Public Route Guard: Call on login.html to redirect already logged in users to dashboard
   */
  async function redirectIfAuthenticated() {
    if (isAuthenticated()) {
      const profile = await fetchCurrentUser();
      if (profile && profile.user) {
        window.location.href = 'dashboard.html';
      }
    }
  }

  /**
   * Update Dashboard UI elements with authenticated user info
   */
  function applyUserToDashboard(user) {
    if (!user) return;

    // Mini profile in sidebar footer
    const nameEl = document.querySelector('.user-name');
    const roleEl = document.querySelector('.user-role');
    const avatarEls = document.querySelectorAll('.avatar');

    const initials = `${user.first_name ? user.first_name[0] : ''}${user.last_name ? user.last_name[0] : ''}`.toUpperCase() || 'U';

    if (nameEl) {
      nameEl.textContent = `${user.first_name} ${user.last_name}`;
      nameEl.style.cursor = 'pointer';
      nameEl.title = 'View & Edit Profile';
      nameEl.onclick = () => window.location.href = 'profile.html';
    }
    if (roleEl) roleEl.textContent = user.role;
    avatarEls.forEach(el => {
      el.textContent = initials;
      el.setAttribute('title', `${user.first_name} ${user.last_name} (${user.role}) - View Profile`);
      el.style.cursor = 'pointer';
      el.onclick = () => window.location.href = 'profile.html';
    });

    // Wire up sidebar logout button if present
    const logoutBtn = document.querySelector('a[title="Sign out"]');
    if (logoutBtn) {
      logoutBtn.setAttribute('href', '#');
      logoutBtn.onclick = (e) => {
        e.preventDefault();
        logout();
      };
    }
  }

  /**
   * Hide UI navigation elements based on database role permissions and strict role maps
   */
  function applyPermissionVisibility(user) {
    if (!user) return;
    const role = (user.role || '').trim();
    const permissions = user.permissions || [];
    const isAdmin = role === 'Admin';

    const linkPermissions = {
      'customers.html': 'customers.view',
      'leads.html': 'leads.view',
      'deals.html': 'deals.view',
      'tasks.html': 'tasks.view',
      'calls.html': 'calls.view',
      'meetings.html': 'meetings.view',
      'calendar.html': ['meetings.view', 'calls.view', 'tasks.view'],
      'products.html': 'products.view',
      'invoices.html': 'invoices.view',
      'payments.html': 'payments.view',
      'emails.html': ['customers.view', 'leads.view', 'deals.view'],
      'reports.html': 'reports.view',
      'users.html': 'users.view',
      'audit-logs.html': 'admin.only',
      'settings.html': 'settings.view'
    };

    const roleAllowedPages = {
      'Admin': null, // All pages allowed
      'Manager': ['dashboard.html', 'customers.html', 'leads.html', 'deals.html', 'tasks.html', 'calls.html', 'meetings.html', 'calendar.html', 'products.html', 'invoices.html', 'payments.html', 'emails.html', 'notifications.html', 'reports.html', 'users.html', 'settings.html', 'profile.html'],
      'Sales Employee': ['dashboard.html', 'customers.html', 'leads.html', 'deals.html', 'tasks.html', 'calls.html', 'meetings.html', 'calendar.html', 'emails.html', 'notifications.html', 'profile.html'],
      'Sales': ['dashboard.html', 'customers.html', 'leads.html', 'deals.html', 'tasks.html', 'calls.html', 'meetings.html', 'calendar.html', 'emails.html', 'notifications.html', 'profile.html'],
      'Staff': ['dashboard.html', 'customers.html', 'tasks.html', 'calls.html', 'meetings.html', 'products.html', 'emails.html', 'notifications.html', 'profile.html']
    };

    function userHasLinkPermission(href) {
      if (isAdmin) return true;
      if (!href) return true;
      const filename = href.split('/').pop().split('?')[0];
      if (!filename || filename === 'dashboard.html' || filename === 'notifications.html' || filename === 'emails.html' || filename === 'profile.html') {
        return true;
      }

      // Check role fallback first if present
      const allowedForRole = roleAllowedPages[role];
      if (allowedForRole !== undefined && allowedForRole !== null) {
        if (!allowedForRole.includes(filename)) {
          return false;
        }
      }

      // Check permission array if available
      const required = linkPermissions[filename];
      if (!required) return true;
      if (required === 'admin.only') return false;
      if (Array.isArray(required)) {
        return required.some(p => permissions.includes(p));
      }
      return permissions.includes(required);
    }

    // 1. Process all sidebar nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      const link = item.querySelector('a');
      const href = link ? link.getAttribute('href') : '';
      const explicitPerm = item.getAttribute('data-permission');

      let allowed = userHasLinkPermission(href);
      if (explicitPerm && !isAdmin && explicitPerm !== 'notifications.view' && explicitPerm !== 'emails.view') {
        allowed = allowed && permissions.includes(explicitPerm);
      }

      item.style.display = allowed ? '' : 'none';
    });

    // 2. Hide empty section titles if all items below them are hidden
    document.querySelectorAll('.sidebar-content').forEach(container => {
      const titles = container.querySelectorAll('.nav-section-title');
      titles.forEach(title => {
        let nextEl = title.nextElementSibling;
        while (nextEl && !nextEl.classList.contains('nav-menu')) {
          nextEl = nextEl.nextElementSibling;
        }
        if (nextEl && nextEl.classList.contains('nav-menu')) {
          const visibleItems = Array.from(nextEl.children).filter(child => child.style.display !== 'none');
          title.style.display = visibleItems.length > 0 ? '' : 'none';
        }
      });
    });
  }

  /**
   * Initialize login form handlers with full validation and loading states
   */
  function initLoginForm(formId, alertId) {
    const form = document.getElementById(formId);
    const alertBox = document.getElementById(alertId);

    if (!form) return;

    // Check if session just expired
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('session') === 'expired') {
      showAlert(alertBox, 'Your session has expired. Please log in again.', 'warning');
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const emailInput = form.querySelector('input[type="email"]');
      const passwordInput = form.querySelector('input[type="password"]');
      const rememberInput = form.querySelector('input[type="checkbox"]');
      const submitBtn = form.querySelector('button[type="submit"]');

      let email = emailInput ? emailInput.value.trim() : '';
      const password = passwordInput ? passwordInput.value : '';
      const remember = rememberInput ? rememberInput.checked : false;

      // Basic client-side checks
      if (!email || !password) {
        showAlert(alertBox, 'Please enter both email and password.', 'danger');
        return;
      }

      // Auto-expand shorthand usernames (e.g. 'admin' -> 'admin@crm.local')
      if (!email.includes('@')) {
        const defaultRoles = ['admin', 'manager', 'sales', 'staff', 'inactive'];
        if (defaultRoles.includes(email.toLowerCase())) {
          email = `${email.toLowerCase()}@crm.local`;
          if (emailInput) emailInput.value = email;
        }
      } else if (email.toLowerCase().endsWith('@localhost')) {
        email = email.replace(/@localhost$/i, '@crm.local');
        if (emailInput) emailInput.value = email;
      } else if (email.toLowerCase().endsWith('@crm')) {
        email = `${email}.local`;
        if (emailInput) emailInput.value = email;
      }

      // Enter loading state
      const originalBtnText = submitBtn ? submitBtn.innerHTML : 'Sign In';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="btn-spinner"></span> Authenticating...';
      }
      hideAlert(alertBox);

      try {
        const result = await login(email, password, remember);

        if (!result.success) {
          showAlert(alertBox, result.message, 'danger');
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
          }
          return;
        }

        showAlert(alertBox, 'Login successful! Redirecting to dashboard...', 'success');

        setTimeout(() => {
          window.location.href = 'dashboard.html';
        }, 600);
      } catch (err) {
        showAlert(alertBox, 'An unexpected error occurred. Please try again.', 'danger');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnText;
        }
      }
    });
  }

  function showAlert(alertElement, message, type = 'info') {
    if (!alertElement) return;
    alertElement.className = `alert alert-${type} visible`;
    alertElement.textContent = message;
  }

  function hideAlert(alertElement) {
    if (!alertElement) return;
    alertElement.className = 'alert';
    alertElement.textContent = '';
  }

  return {
    isAuthenticated,
    getUser,
    login,
    logout,
    fetchCurrentUser,
    hasPermission,
    hasRole,
    requireAuth,
    redirectIfAuthenticated,
    applyPermissionVisibility,
    initLoginForm,
    showAlert,
  };
})();

// Attach to global window
if (typeof window !== 'undefined') {
  window.Auth = Auth;
}
