import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AdminApiError,
  fetchAuditEvents,
  fetchAdminTab,
  fetchUsers,
  request,
  revokeSessions,
  signIn,
} from '../src/adminApi.js';

const jsonResponse = (payload, status = 200) => new Response(
  JSON.stringify(payload),
  { status, headers: { 'Content-Type': 'application/json' } },
);

test('admin sign-in validates the server-side administrator claim', async () => {
  const calls = [];
  const session = await signIn('admin@example.test', 'correct-horse-42', async (path, options) => {
    calls.push({ path, options });
    return jsonResponse({
      access_token: 'admin-token',
      user: { email: 'admin@example.test', is_admin: true },
    });
  });
  assert.equal(session.access_token, 'admin-token');
  assert.equal(calls[0].path, '/api/auth/signin');
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    email: 'admin@example.test',
    password: 'correct-horse-42',
  });
});

test('ordinary accounts are rejected and their new session is revoked', async () => {
  const paths = [];
  await assert.rejects(
    signIn('learner@example.test', 'correct-horse-42', async (path) => {
      paths.push(path);
      if (path === '/api/auth/signin') {
        return jsonResponse({
          access_token: 'learner-token',
          user: { email: 'learner@example.test', is_admin: false },
        });
      }
      return new Response(null, { status: 204 });
    }),
    (error) => error instanceof AdminApiError && error.status === 403,
  );
  assert.deepEqual(paths, ['/api/auth/signin', '/api/auth/signout']);
});

test('admin reads send the bearer token and never substitute mock data', async () => {
  const result = await fetchAdminTab('Overview', 'secret-token', async (path, options) => {
    assert.equal(path, '/admin/dashboard');
    assert.equal(options.headers.Authorization, 'Bearer secret-token');
    return jsonResponse({ health: {}, users: {} });
  });
  assert.deepEqual(result, { health: {}, users: {} });
});

test('revocation sends a reason in an authenticated JSON request', async () => {
  await revokeSessions('user-id', 'Suspected credential theft', 'secret-token', async (path, options) => {
    assert.equal(path, '/admin/users/user-id/revoke');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers.Authorization, 'Bearer secret-token');
    assert.deepEqual(JSON.parse(options.body), { reason: 'Suspected credential theft' });
    return jsonResponse({
      status: 'success',
      revoked_count: 2,
      audit_event_id: 'audit-id',
    });
  });
});

test('user directory search and audit history use bounded page parameters', async () => {
  await fetchUsers(
    { query: ' learner@example.test ', page: 2, pageSize: 25 },
    'secret-token',
    async (path, options) => {
      assert.equal(
        path,
        '/admin/users?page=2&page_size=25&query=learner%40example.test',
      );
      assert.equal(options.headers.Authorization, 'Bearer secret-token');
      return jsonResponse({ items: [], page: 2, page_size: 25, total: 0 });
    },
  );

  await fetchAuditEvents(
    { page: 3, pageSize: 50 },
    'secret-token',
    async (path, options) => {
      assert.equal(path, '/admin/audit-events?page=3&page_size=50');
      assert.equal(options.headers.Authorization, 'Bearer secret-token');
      return jsonResponse({ items: [], page: 3, page_size: 50, total: 0 });
    },
  );
});

test('safe backend errors are surfaced as typed failures', async () => {
  await assert.rejects(
    fetchAdminTab('Errors', 'secret-token', async () => jsonResponse(
      { detail: 'administrative data is temporarily unavailable' },
      503,
    )),
    (error) => (
      error instanceof AdminApiError
      && error.status === 503
      && error.message === 'administrative data is temporarily unavailable'
    ),
  );
});

test('hung backend requests are aborted with a bounded timeout', async () => {
  await assert.rejects(
    request('/admin/dashboard', {
      token: 'secret-token',
      timeoutMs: 5,
      fetchImpl: async (_path, options) => new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => {
          reject(new DOMException('aborted', 'AbortError'));
        });
      }),
    }),
    (error) => (
      error instanceof AdminApiError
      && error.message === 'The backend request timed out.'
    ),
  );
});
