export const API = {
  projects: '/api/projects',
  springDeployments: '/api/deployment-spring',
  auth: '/api/auth',
  operations: '/api/orchestrator',
  builds: '/api/build',
  deployments: '/api/deployment'
};

export async function request(url, token, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });

  const raw = await response.text();
  let data;

  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = { detail: raw.trim().startsWith('<') ? 'Service unavailable. Please retry after startup.' : raw || 'Invalid server response' };
  }

  if (!response.ok) {
    if (response.status === 401 && token) {
      window.dispatchEvent(
        new CustomEvent('devsphere:auth-expired', {
          detail: { token }
        })
      );
    }

    const detail = data.detail;
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map(error =>
            `${(error.loc || []).join('.')}: ${error.msg}`
          ).join('; ')
        : JSON.stringify(detail || data);

    throw new Error(
      `HTTP ${response.status}: ${message}`
    );
  }

  return data;
}
