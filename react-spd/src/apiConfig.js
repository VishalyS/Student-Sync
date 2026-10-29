// Central API Base and Endpoint Helper for Student Sync
// In local development under Vite, default to empty string so requests leverage Vite's proxy.
// In custom/production deployments, VITE_API_BASE_URL can specify the target host if required.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export const getApiUrl = (endpoint) => {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return API_BASE ? `${API_BASE}${cleanEndpoint}` : cleanEndpoint;
};

// Seamless global routing for API calls across all components:
// If VITE_API_BASE_URL is configured (e.g. Render backend URL in Vercel production),
// relative `/api/*` calls are routed to the remote backend.
// In local development, they remain relative to use Vite dev proxy.
if (typeof window !== 'undefined' && window.fetch && API_BASE) {
  const _origFetch = window.fetch;
  window.fetch = function (input, init) {
    if (typeof input === 'string' && input.startsWith('/api')) {
      input = getApiUrl(input);
    }
    return _origFetch.call(this, input, init);
  };
}

export default {
  API_BASE,
  getApiUrl
};
