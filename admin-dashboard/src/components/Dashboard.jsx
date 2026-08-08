import React, { useState, useEffect, useCallback } from 'react';
import SystemHealth from './SystemHealth';
import UserManagement from './UserManagement';
import LearningPanel from './LearningPanel';
import RoleplayPanel from './RoleplayPanel';
import ErrorFeed from './ErrorFeed';

const TABS = ['Overview', 'Learning', 'Roleplay', 'Errors'];

const MOCK = {
  overview: {
    health: {
      status: 'warning', postgres: 'healthy', ollama: 'healthy',
      groq_quota: 'ok', plp_workers: 1, active_jobs: 3,
      models: { whisperx: false, pronunciation: false, grammar: true, tts: false },
    },
    users: {
      total_registered: 1250, total_guests: 843, active_sessions: 42,
      recent_registrations: [
        { id: 'u-101', email: 'learner@example.com', type: 'registered', created_at: '2026-08-06T10:00:00Z' },
        { id: 'u-102', email: 'guest', type: 'guest', created_at: '2026-08-06T14:30:00Z' },
      ],
    },
  },
  learning: {
    lessons: { total: 4200, ready: 3800, pending: 340, failed: 60 },
    jobs_by_status: { complete: 210, idle: 14, queued: 3, failed: 7 },
    lessons_by_type: { vocabulary: 900, grammar: 800, listening: 700, speaking: 600, reading: 500, pronunciation: 400, discourse: 200, assessment: 100 },
  },
  roleplay: {
    total_sessions: 3870, sessions_today: 42, active_now: 5,
    avg_fluency: 71.4, avg_prosody: 68.2, avg_word_confidence: 79.1, avg_alignment_coverage: 0.83,
    recent_sessions: [
      { id: 'r-1', scenario: 'Job interview at a tech company', cefr_level: 'B2', status: 'completed', message_count: 18, average_fluency: 74, created_at: '2026-08-06T15:00:00Z' },
      { id: 'r-2', scenario: 'Ordering food at a restaurant', cefr_level: 'B1', status: 'active', message_count: 6, average_fluency: null, created_at: '2026-08-06T17:40:00Z' },
    ],
  },
  errors: {
    errors: [
      { job_id: 'aabbccdd-0000-0000-0000-000000000001', error: 'rate_limited: Groq token window full. Retry after 60s.', attempts: 3, updated_at: '2026-08-06T16:22:00Z' },
    ],
  },
};

const ENDPOINTS = {
  Overview: '/admin/dashboard',
  Learning: '/admin/learning',
  Roleplay: '/admin/roleplay',
  Errors: '/admin/errors',
};

const MOCK_KEYS = {
  Overview: 'overview',
  Learning: 'learning',
  Roleplay: 'roleplay',
  Errors: 'errors',
};

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('Overview');
  const [tabData, setTabData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTab = useCallback(async (tab) => {
    try {
      const response = await fetch(ENDPOINTS[tab]);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      setTabData((prev) => ({ ...prev, [tab]: result }));
      setError(null);
    } catch (err) {
      console.error(`Failed to fetch ${tab}:`, err);
      setError('Backend unreachable — showing mock data.');
      setTabData((prev) => ({ ...prev, [tab]: MOCK[MOCK_KEYS[tab]] }));
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch active tab on mount and every 10s
  useEffect(() => {
    setLoading(true);
    fetchTab(activeTab);
    const interval = setInterval(() => fetchTab(activeTab), 10000);
    return () => clearInterval(interval);
  }, [activeTab, fetchTab]);

  const data = tabData[activeTab];

  return (
    <div className="dashboard-container">
      <h1>SpeakFlow Operations</h1>

      {/* Tab Bar */}
      <nav style={{ display: 'flex', gap: '0.25rem', marginBottom: '2rem', background: 'rgba(255,255,255,0.04)', padding: '0.35rem', borderRadius: 'var(--radius-lg)', width: 'fit-content' }}>
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              background: activeTab === tab ? 'var(--primary-color)' : 'transparent',
              color: activeTab === tab ? 'white' : 'var(--text-secondary)',
              border: 'none',
              padding: '0.5rem 1.25rem',
              borderRadius: 'calc(var(--radius-lg) - 4px)',
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontWeight: activeTab === tab ? 600 : 400,
              fontSize: '0.9rem',
              transition: 'var(--transition)',
            }}
          >
            {tab}
          </button>
        ))}
      </nav>

      {/* Error Banner */}
      {error && (
        <div className="glass-card" style={{ borderLeft: '4px solid var(--warning)', marginBottom: '1.5rem' }}>
          <p style={{ color: 'var(--warning)' }}>⚠ {error}</p>
        </div>
      )}

      {/* Tab Content */}
      {loading ? (
        <div className="glass-card" style={{ textAlign: 'center', padding: '4rem' }}>
          <p className="animate-pulse">Loading {activeTab}...</p>
        </div>
      ) : (
        <div className="dashboard-grid">
          {activeTab === 'Overview' && data && (
            <>
              <SystemHealth health={data.health} />
              <UserManagement users={data.users} onRevoke={() => fetchTab('Overview')} />
            </>
          )}
          {activeTab === 'Learning' && <LearningPanel data={data} />}
          {activeTab === 'Roleplay' && <RoleplayPanel data={data} />}
          {activeTab === 'Errors' && <ErrorFeed data={data} />}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
