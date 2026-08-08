import React from 'react';

const ScoreBar = ({ label, value }) => (
  <div style={{ marginBottom: '1rem' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ color: 'var(--primary-color)', fontWeight: 700 }}>
        {value !== null && value !== undefined ? `${value}/100` : '—'}
      </span>
    </div>
    <div style={{ height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '9999px', overflow: 'hidden' }}>
      <div style={{
        height: '100%',
        width: value !== null && value !== undefined ? `${value}%` : '0%',
        background: 'linear-gradient(90deg, var(--primary-color), var(--secondary-color))',
        borderRadius: '9999px',
        transition: 'width 0.6s ease',
      }} />
    </div>
  </div>
);

const CEFR_COLORS = { A1: '#64748b', A2: '#64748b', B1: '#3b82f6', B2: '#6366f1', C1: '#a855f7', C2: '#ec4899' };

const RoleplayPanel = ({ data }) => {
  if (!data) return null;

  return (
    <div style={{ display: 'contents' }}>
      {/* Top Stats */}
      <div className="glass-card">
        <h2>Session Stats</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginTop: '1rem' }}>
          {[
            { label: 'Total Sessions', value: data.total_sessions },
            { label: 'Today', value: data.sessions_today },
            { label: 'Active Now', value: data.active_now },
          ].map(({ label, value }) => (
            <div key={label} style={{ textAlign: 'center' }}>
              <div className="stat-value" style={{ fontSize: '2rem', color: 'var(--secondary-color)' }}>{value}</div>
              <div className="stat-label">{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Average Scores */}
      <div className="glass-card">
        <h2>Average Scores</h2>
        <p style={{ marginBottom: '1.5rem', fontSize: '0.875rem' }}>Across all completed sessions</p>
        <ScoreBar label="Fluency" value={data.avg_fluency} />
        <ScoreBar label="Prosody" value={data.avg_prosody} />
        <ScoreBar label="Word Confidence" value={data.avg_word_confidence} />
        <ScoreBar label="Alignment Coverage" value={data.avg_alignment_coverage} />
      </div>

      {/* Recent Sessions Table */}
      <div className="glass-card" style={{ gridColumn: 'span 2' }}>
        <h2>Recent Sessions</h2>
        <div className="glass-table-container" style={{ marginTop: '1rem' }}>
          <table className="glass-table">
            <thead>
              <tr>
                <th>Scenario</th>
                <th>CEFR</th>
                <th>Status</th>
                <th>Messages</th>
                <th>Fluency</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_sessions.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>No sessions yet</td>
                </tr>
              ) : data.recent_sessions.map((s) => (
                <tr key={s.id}>
                  <td style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.scenario}
                  </td>
                  <td>
                    <span style={{
                      background: `${CEFR_COLORS[s.cefr_level] || '#64748b'}22`,
                      color: CEFR_COLORS[s.cefr_level] || '#64748b',
                      padding: '0.15rem 0.5rem',
                      borderRadius: '9999px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                    }}>
                      {s.cefr_level}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge ${s.status === 'completed' ? 'healthy' : s.status === 'active' ? 'warning' : ''}`}
                      style={{ fontSize: '0.65rem' }}>
                      {s.status}
                    </span>
                  </td>
                  <td>{s.message_count}</td>
                  <td>{s.average_fluency !== null ? `${s.average_fluency}/100` : '—'}</td>
                  <td style={{ fontSize: '0.8rem' }}>{new Date(s.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default RoleplayPanel;
