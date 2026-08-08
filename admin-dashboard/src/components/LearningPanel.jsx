import React from 'react';

const STATUS_COLORS = {
  ready: 'var(--success)',
  pending: 'var(--warning)',
  failed: 'var(--danger)',
};

const LearningPanel = ({ data }) => {
  if (!data) return null;

  const { lessons, jobs_by_status, lessons_by_type } = data;
  const total = lessons.total || 1; // avoid division by zero

  return (
    <div style={{ display: 'contents' }}>
      {/* Lesson Content Status */}
      <div className="glass-card">
        <h2>Lesson Content Status</h2>
        <p style={{ marginBottom: '1.5rem' }}>{lessons.total.toLocaleString()} total lessons across all PLPs</p>

        {['ready', 'pending', 'failed'].map((status) => (
          <div key={status} style={{ marginBottom: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
              <span style={{ textTransform: 'capitalize', color: STATUS_COLORS[status] }}>{status}</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                {lessons[status]} <span style={{ color: 'var(--text-secondary)', fontWeight: 400, fontSize: '0.8rem' }}>
                  ({Math.round((lessons[status] / total) * 100)}%)
                </span>
              </span>
            </div>
            <div style={{ height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '9999px', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${Math.round((lessons[status] / total) * 100)}%`,
                background: STATUS_COLORS[status],
                borderRadius: '9999px',
                transition: 'width 0.6s ease',
              }} />
            </div>
          </div>
        ))}
      </div>

      {/* Generation Jobs */}
      <div className="glass-card">
        <h2>Generation Jobs</h2>
        {Object.keys(jobs_by_status).length === 0 ? (
          <p>No jobs found.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {Object.entries(jobs_by_status).map(([status, count]) => (
              <div key={status} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  {status}
                </span>
                <span style={{
                  background: 'rgba(255,255,255,0.07)',
                  padding: '0.15rem 0.6rem',
                  borderRadius: '9999px',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                }}>
                  {count}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Lesson Type Breakdown */}
      <div className="glass-card" style={{ gridColumn: 'span 2' }}>
        <h2>Lesson Type Breakdown</h2>
        {Object.keys(lessons_by_type).length === 0 ? (
          <p>No lesson data found.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '1rem', marginTop: '0.5rem' }}>
            {Object.entries(lessons_by_type)
              .sort((a, b) => b[1] - a[1])
              .map(([type, count]) => (
                <div key={type} className="glass-card" style={{ textAlign: 'center', padding: '1rem' }}>
                  <div className="stat-value" style={{ fontSize: '1.75rem' }}>{count}</div>
                  <div className="stat-label" style={{ marginTop: '0.25rem', textTransform: 'none' }}>
                    {type.replace(/_/g, ' ')}
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default LearningPanel;
