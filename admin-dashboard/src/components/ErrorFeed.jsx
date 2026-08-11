import React from 'react';

const ErrorFeed = ({ data }) => {
  if (!data) return null;

  const { errors } = data;

  return (
    <div className="glass-card" style={{ gridColumn: 'span 2' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0 }}>Generation Job Failures</h2>
        <span style={{
          background: errors.length > 0 ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)',
          color: errors.length > 0 ? 'var(--danger)' : 'var(--success)',
          border: `1px solid ${errors.length > 0 ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'}`,
          padding: '0.25rem 0.75rem',
          borderRadius: '9999px',
          fontSize: '0.8rem',
          fontWeight: 600,
        }}>
          {errors.length} {errors.length === 1 ? 'failure' : 'failures'}
        </span>
      </div>

      {errors.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem 0' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
          <p style={{ color: 'var(--success)' }}>No failed generation jobs. Everything is running smoothly.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '600px', overflowY: 'auto' }}>
          {errors.map((err) => (
            <div key={err.job_id} style={{
              background: 'rgba(239,68,68,0.07)',
              border: '1px solid rgba(239,68,68,0.2)',
              borderLeft: '3px solid var(--danger)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', gap: '1rem' }}>
                <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-secondary)', flexShrink: 0 }}>
                  job: {err.job_id.slice(0, 8)}…
                </span>
                <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  <span>attempts: <strong style={{ color: 'var(--text-primary)' }}>{err.attempts}</strong></span>
                  <span>{new Date(err.updated_at).toLocaleString()}</span>
                </div>
              </div>
              <pre style={{
                margin: 0,
                fontSize: '0.8rem',
                color: 'var(--danger)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontFamily: 'monospace',
              }}>
                [{err.failure_kind}] {err.message}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ErrorFeed;
