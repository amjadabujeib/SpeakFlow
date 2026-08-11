export class AdminApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'AdminApiError';
    this.status = status;
  }
}

export async function request(
  path,
  {
    token,
    method = 'GET',
    body,
    fetchImpl = fetch,
    timeoutMs = 8000,
  } = {},
) {
  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let response;
  try {
    response = await fetchImpl(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'omit',
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted) {
      throw new AdminApiError('The backend request timed out.');
    }
    throw new AdminApiError('The backend could not be reached.');
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) {
    let detail = '';
    try {
      const payload = await response.json();
      detail = typeof payload.detail === 'string' ? payload.detail : '';
    } catch {
      // A safe status-based message is used when the body is not JSON.
    }
    throw new AdminApiError(detail || `Request failed with HTTP ${response.status}.`, response.status);
  }
  if (response.status === 204) return null;
  return response.json();
}

export async function signIn(email, password, fetchImpl) {
  const session = await request('/api/auth/signin', {
    method: 'POST',
    body: { email, password },
    fetchImpl,
  });
  if (session?.user?.is_admin !== true) {
    if (session?.access_token) {
      await signOut(session.access_token, fetchImpl).catch(() => {});
    }
    throw new AdminApiError('This account is not authorized for administration.', 403);
  }
  return session;
}

export const signOut = (token, fetchImpl) => request('/api/auth/signout', {
  token,
  method: 'POST',
  fetchImpl,
});

const ADMIN_ENDPOINTS = {
  Overview: '/admin/dashboard',
  Learning: '/admin/learning',
  Roleplay: '/admin/roleplay',
  Errors: '/admin/errors',
};

export function fetchAdminTab(tab, token, fetchImpl) {
  const path = ADMIN_ENDPOINTS[tab];
  if (!path) throw new AdminApiError('Unknown dashboard tab.');
  return request(path, { token, fetchImpl });
}

export function fetchUsers({ query = '', page = 1, pageSize = 25 } = {}, token, fetchImpl) {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (query.trim()) parameters.set('query', query.trim());
  return request(`/admin/users?${parameters}`, { token, fetchImpl });
}

export function fetchAuditEvents({ page = 1, pageSize = 50 } = {}, token, fetchImpl) {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return request(`/admin/audit-events?${parameters}`, { token, fetchImpl });
}

export const revokeSessions = (userId, reason, token, fetchImpl) => request(
  `/admin/users/${encodeURIComponent(userId)}/revoke`,
  { token, method: 'POST', body: { reason }, fetchImpl },
);
