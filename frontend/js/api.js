/**
 * CRM Reusable API Client Helper
 * Modular HTTP request layer with automated JWT Bearer token attachment,
 * response code handling (200, 201, 400, 401, 403, 404, 500), and safe session expiration redirection.
 */

const ApiClient = (() => {
  const TOKEN_KEY = 'crm_access_token';
  const REMEMBER_KEY = 'crm_remember_session';

  // Default API configuration
  const CONFIG = {
    baseUrl: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'http://127.0.0.1:5000'
      : '',
    timeout: 10000,
  };

  /**
   * Retrieve active authentication token from localStorage or sessionStorage
   */
  function getToken() {
    return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY) || null;
  }

  /**
   * Store token according to persistence preference (localStorage for remember me, sessionStorage otherwise)
   */
  function setToken(token, remember = false) {
    if (remember) {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(REMEMBER_KEY, 'true');
      sessionStorage.removeItem(TOKEN_KEY);
    } else {
      sessionStorage.setItem(TOKEN_KEY, token);
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REMEMBER_KEY);
    }
  }

  /**
   * Clear all stored authentication tokens and credentials
   */
  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REMEMBER_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  }

  /**
   * Safe redirection to login page without infinite loop
   */
  function handleUnauthorizedRedirect() {
    clearToken();
    const currentPath = window.location.pathname.toLowerCase();
    if (!currentPath.endsWith('login.html') && !currentPath.endsWith('index.html')) {
      console.warn('[ApiClient] Session expired or invalid. Redirecting to login.');
      window.location.href = 'login.html?session=expired';
    }
  }

  /**
   * Core request function
   * @param {string} endpoint - API endpoint path (e.g. '/api/auth/me')
   * @param {object} options - Fetch options (method, headers, body)
   * @returns {Promise<{success: boolean, data?: any, error?: string, status: number}>}
   */
  async function request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${CONFIG.baseUrl}${endpoint}`;

    const headers = {
      'Accept': 'application/json',
      ...options.headers,
    };

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    // Automatically attach Bearer token if present and not explicitly provided
    const token = getToken();
    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
      ...options,
      method: options.method || 'GET',
      headers,
    };

    if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(url, config);
      const isJson = (response.headers.get('content-type') || '').includes('application/json');
      const data = isJson ? await response.json() : await response.text();

      // Handle specific HTTP Status Codes
      if (response.status === 401) {
        // Only trigger redirect on protected endpoints, not on failed login attempts
        if (!endpoint.includes('/api/auth/login')) {
          handleUnauthorizedRedirect();
        }
        return {
          success: false,
          status: 401,
          error: (data && data.message) || 'Unauthorized: Invalid or expired session',
          data,
        };
      }

      if (response.status === 403) {
        return {
          success: false,
          status: 403,
          error: (data && data.message) || 'Forbidden: Insufficient permissions',
          data,
        };
      }

      if (response.status === 400) {
        return {
          success: false,
          status: 400,
          error: (data && data.message) || 'Bad Request: Missing or invalid fields',
          data,
        };
      }

      if (response.status === 404) {
        return {
          success: false,
          status: 404,
          error: (data && data.message) || 'Resource not found',
          data,
        };
      }

      if (response.status >= 500) {
        return {
          success: false,
          status: response.status,
          error: (data && data.message) || 'Internal server error occurred',
          data,
        };
      }

      // Success status codes (200, 201)
      return {
        success: true,
        status: response.status,
        data,
      };
    } catch (err) {
      console.warn(`[ApiClient] Request to ${url} failed:`, err.message);
      return {
        success: false,
        status: 0,
        error: err.message || 'Network request failed or server is unreachable',
        data: null,
      };
    }
  }

  return {
    setBaseUrl(url) {
      CONFIG.baseUrl = url.replace(/\/+$/, '');
    },
    getBaseUrl() {
      return CONFIG.baseUrl;
    },
    getToken,
    setToken,
    clearToken,
    get(endpoint, headers = {}) {
      return request(endpoint, { method: 'GET', headers });
    },
    post(endpoint, body, headers = {}) {
      return request(endpoint, { method: 'POST', body, headers });
    },
    put(endpoint, body, headers = {}) {
      return request(endpoint, { method: 'PUT', body, headers });
    },
    delete(endpoint, headers = {}) {
      return request(endpoint, { method: 'DELETE', headers });
    },
    upload(endpoint, formData, headers = {}) {
      return request(endpoint, { method: 'POST', body: formData, headers });
    },
    checkHealth() {
      return request('/api/health');
    },
  };
})();

// Attach to global window
if (typeof window !== 'undefined') {
  window.ApiClient = ApiClient;
}
