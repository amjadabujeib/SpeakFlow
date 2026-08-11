import React, { useCallback, useEffect, useState } from 'react';
import { fetchAuditEvents } from '../adminApi';

const AuditLog = ({ token, onAuthorizationLost }) => {
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fetchAuditEvents({ page }, token));
      setError(null);
    } catch (requestError) {
      if (requestError.status === 401 || requestError.status === 403) {
        onAuthorizationLost();
        return;
      }
      setError(requestError.message || 'The audit history is unavailable.');
    } finally {
      setLoading(false);
    }
  }, [onAuthorizationLost, page, token]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <section className="glass-card full-width-card">
      <div className="panel-heading">
        <div>
          <h2>Administrator audit history</h2>
          <p>Immutable records of privilege changes and session revocations.</p>
        </div>
        {data && <span className="result-count">{data.total} event(s)</span>}
      </div>

      {error && (
        <div className="error-panel" role="alert">
          <span>{error}</span>
          <button className="btn btn-primary" type="button" onClick={load}>Retry</button>
        </div>
      )}
      {loading && !data ? <p className="loading-message">Loading audit history…</p> : (
        <div className="glass-table-container">
          <table className="glass-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Target</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((event) => (
                <tr key={event.id}>
                  <td>{new Date(event.created_at).toLocaleString()}</td>
                  <td><span className="status-badge warning">{event.action}</span></td>
                  <td className="monospace-cell">{event.actor_user_id || 'local CLI'}</td>
                  <td className="monospace-cell">{event.target_user_id || 'deleted user'}</td>
                  <td className="audit-detail">{JSON.stringify(event.detail)}</td>
                </tr>
              ))}
              {data?.items.length === 0 && (
                <tr><td colSpan="5" className="empty-cell">No audit events</td></tr>
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

export default AuditLog;
