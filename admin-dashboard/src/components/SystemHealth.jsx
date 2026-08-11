import React from 'react';

const SystemHealth = ({ health }) => {
  if (!health) return null;

  return (
    <div className="glass-card">
      <h2>System & ML Health</h2>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <span className="stat-label">Overall Status</span>
        <span className={`status-badge ${health.status === 'healthy' ? 'healthy' : health.status === 'warning' ? 'warning' : 'error'}`}>
          {health.status}
        </span>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <span>PostgreSQL</span>
          <span style={{ color: health.postgres === 'healthy' ? 'var(--success)' : 'var(--danger)' }}>
            {health.postgres}
          </span>
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <span>Ollama (Embeddings)</span>
          <span style={{ color: health.ollama === 'healthy' ? 'var(--success)' : 'var(--danger)' }}>
            {health.ollama}
          </span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <span>Groq Configuration</span>
          <span style={{ color: health.groq === 'configured' ? 'var(--success)' : 'var(--warning)' }}>
            {health.groq}
          </span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <span>Reviewed Curriculum</span>
          <span style={{ color: health.curriculum === 'ready' ? 'var(--success)' : 'var(--danger)' }}>
            {health.curriculum}
          </span>
        </div>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-secondary)' }}>PLP Workers</h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div>
            <div className="stat-value">{health.plp_workers}</div>
            <div className="stat-label">Active Workers</div>
          </div>
          <div>
            <div className="stat-value">{health.active_jobs}</div>
            <div className="stat-label">Jobs in Queue</div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-secondary)' }}>Lazy Models Loaded</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.875rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>WhisperX</span>
            <span style={{ color: health.models?.whisperx ? 'var(--success)' : 'var(--text-secondary)' }}>
              {health.models?.whisperx ? 'Loaded' : 'Sleeping'}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Wav2Vec2</span>
            <span style={{ color: health.models?.pronunciation ? 'var(--success)' : 'var(--text-secondary)' }}>
              {health.models?.pronunciation ? 'Loaded' : 'Sleeping'}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Grammar (GECToR)</span>
            <span style={{ color: health.models?.grammar ? 'var(--success)' : 'var(--text-secondary)' }}>
              {health.models?.grammar ? 'Loaded' : 'Sleeping'}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>TTS (Kokoro)</span>
            <span style={{ color: health.models?.tts ? 'var(--success)' : 'var(--text-secondary)' }}>
              {health.models?.tts ? 'Loaded' : 'Sleeping'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemHealth;
