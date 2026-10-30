// Central API Base and Endpoint Helper for Student Sync
// In local development under Vite, default to empty string so requests leverage Vite's proxy.
// In custom/production deployments, VITE_API_BASE_URL specifies the target host, defaulting to Render.

const DEFAULT_PROD_API_URL = 'https://student-sync-api.onrender.com';

export const resolveApiBase = () => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, '');
  }
  // In Vite production bundle, default to deployed Render backend
  if (import.meta.env.PROD) {
    return DEFAULT_PROD_API_URL;
  }
  // Runtime fallback: if accessed on any domain other than localhost/127.0.0.1 in the browser
  if (typeof window !== 'undefined' && window.location && window.location.hostname) {
    const host = window.location.hostname;
    if (host !== 'localhost' && host !== '127.0.0.1' && !host.startsWith('192.168.')) {
      return DEFAULT_PROD_API_URL;
    }
  }
  // Local development default (uses Vite proxy)
  return '';
};

export const API_BASE = resolveApiBase();

export const getApiUrl = (endpoint) => {
  if (!endpoint || typeof endpoint !== 'string') return endpoint;
  // If already absolute URL, return unchanged
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }
  const base = resolveApiBase();
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return base ? `${base}${cleanEndpoint}` : cleanEndpoint;
};

// Seamless global routing for API calls across all components:
// If API_BASE is configured (e.g. Render backend URL in Vercel production),
// relative `/api/*` and related endpoints are routed to the remote backend.
// In local development, they remain relative to use Vite dev proxy.
if (typeof window !== 'undefined' && window.fetch) {
  const _origFetch = window.fetch;
  window.fetch = function (input, init) {
    const base = resolveApiBase();
    if (base) {
      if (typeof input === 'string') {
        if (
          input.startsWith('/api') ||
          input.startsWith('/login') ||
          input.startsWith('/register') ||
          input.startsWith('/stats') ||
          input.startsWith('/profile') ||
          input.startsWith('/notifications') ||
          input.startsWith('/health')
        ) {
          input = getApiUrl(input);
        }
      } else if (input instanceof Request) {
        try {
          const url = new URL(input.url, window.location.origin);
          if (
            url.origin === window.location.origin &&
            (
              url.pathname.startsWith('/api') ||
              url.pathname.startsWith('/login') ||
              url.pathname.startsWith('/register') ||
              url.pathname.startsWith('/stats') ||
              url.pathname.startsWith('/profile') ||
              url.pathname.startsWith('/notifications') ||
              url.pathname.startsWith('/health')
            )
          ) {
            const targetUrl = `${base}${url.pathname}${url.search}`;
            input = new Request(targetUrl, input);
          }
        } catch (e) {
          // If URL parsing fails, continue with original input
        }
      }
    }
    return _origFetch.call(this, input, init);
  };
}

export default {
  API_BASE,
  getApiUrl,
  resolveApiBase
};
