import React, { useCallback, useEffect, useState } from 'react';
import { fetchUsers, revokeSessions } from '../adminApi';

const UserDirectory = ({ token, onAuthorizationLost }) => {
  const [query, setQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [revoking, setRevoking] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fetchUsers({ query: appliedQuery, page }, token));
      setError(null);
    } catch (requestError) {
      if (requestError.status === 401 || requestError.status === 403) {
        onAuthorizationLost();
        return;
      }
      setError(requestError.message || 'The user directory is unavailable.');
    } finally {
      setLoading(false);
    }
  }, [appliedQuery, onAuthorizationLost, page, token]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSearch = (event) => {
    event.preventDefault();
    setPage(1);
    setAppliedQuery(query.trim());
  };

  const handleRevoke = async (user) => {
    const label = user.email || user.display_name || user.id;
    const reason = window.prompt(
      `Why should all active sessions for ${label} be revoked?`,
    )?.trim();
    if (!reason) return;
    if (reason.length < 3 || reason.length > 200) {
      window.alert('Enter a reason between 3 and 200 characters.');
      return;
    }
    if (!window.confirm(
      `Revoke every active session for ${label}? This will sign the user out on all devices.`,
    )) return;

    setRevoking(user.id);
    try {
      const result = await revokeSessions(user.id, reason, token);
      window.alert(
        `Revoked ${result.revoked_count} session(s). Audit event: ${result.audit_event_id}`,
      );
      await load();
    } catch (requestError) {
      if (requestError.status === 401 || requestError.status === 403) {
        onAuthorizationLost();
      } else {
        window.alert(requestError.message || 'Session revocation failed.');
      }
    } finally {
      setRevoking(null);
    }
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <section className="glass-card full-width-card">
      <div className="panel-heading">
        <div>
          <h2>User directory</h2>
          <p>Search every account by email, display name, or exact UUID.</p>
        </div>
        {data && <span className="result-count">{data.total} account(s)</span>}
      </div>

      <form className="directory-toolbar" onSubmit={handleSearch}>
        <input
          aria-label="Search users"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          maxLength={320}
          placeholder="Email, display name, or UUID"
        />
        <button className="btn btn-primary" type="submit">Search</button>
        {appliedQuery && (
          <button
            className="btn btn-secondary"
            type="button"
            onClick={() => {
              setQuery('');
              setAppliedQuery('');
              setPage(1);
            }}
          >
            Clear
          </button>
        )}
      </form>

      {error && <div className="error-panel" role="alert">{error}</div>}
      {loading && !data ? <p className="loading-message">Loading users…</p> : (
        <div className="glass-table-container">
          <table className="glass-table">
            <thead>
              <tr>
                <th>Account</th>
                <th>Type</th>
                <th>Active sessions</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((user) => (
                <tr key={user.id}>
                  <td>
                    <div>{user.email || user.display_name}</div>
                    <div className="monospace-cell secondary-line">{user.id}</div>
                  </td>
                  <td>
                    <span className={`status-badge ${user.is_admin ? 'warning' : 'healthy'}`}>
                      {user.is_admin ? 'administrator' : user.kind}
                    </span>
                  </td>
                  <td>{user.active_sessions}</td>
                  <td>{new Date(user.created_at).toLocaleString()}</td>
                  <td>
                    <button
                      className="btn btn-danger"
                      type="button"
                      onClick={() => handleRevoke(user)}
                      disabled={revoking === user.id || user.active_sessions === 0}
                    >
                      {revoking === user.id ? 'Revoking…' : 'Revoke sessions'}
                    </button>
                  </td>
                </tr>
              ))}
              {data?.items.length === 0 && (
                <tr><td colSpan="5" className="empty-cell">No matching accounts</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {data && (
        <div className="pagination-controls">
          <button
            className="btn btn-secondary"
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => setPage((value) => value - 1)}
          >
            Previous
          </button>
          <span>Page {page} of {totalPages}</span>
          <button
            className="btn btn-secondary"
            type="button"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </button>
        </div>
      )}
    </section>
  );
};

export default UserDirectory;
