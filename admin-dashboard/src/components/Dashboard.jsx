import React, { useState, useEffect, useCallback } from 'react';
import { fetchAdminTab } from '../adminApi';
import SystemHealth from './SystemHealth';
import UserManagement from './UserManagement';
import LearningPanel from './LearningPanel';
import RoleplayPanel from './RoleplayPanel';
import ErrorFeed from './ErrorFeed';
import UserDirectory from './UserDirectory';
import AuditLog from './AuditLog';

const TABS = ['Overview', 'Users', 'Learning', 'Roleplay', 'Errors', 'Audit'];
const SELF_MANAGED_TABS = new Set(['Users', 'Audit']);

const Dashboard = ({ token, onAuthorizationLost }) => {
  const [activeTab, setActiveTab] = useState('Overview');
  const [tabData, setTabData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTab = useCallback(async (tab) => {
    setLoading(true);
    try {
      const result = await fetchAdminTab(tab, token);
      setTabData((previous) => ({ ...previous, [tab]: result }));
      setError(null);
    } catch (requestError) {
      if (requestError.status === 401 || requestError.status === 403) {
        onAuthorizationLost();
        return;
      }
      setError(requestError.message || 'Operational data is unavailable.');
    } finally {
      setLoading(false);
    }
  }, [onAuthorizationLost, token]);

  useEffect(() => {
    if (SELF_MANAGED_TABS.has(activeTab)) {
      setLoading(false);
      setError(null);
      return undefined;
    }
    fetchTab(activeTab);
    const interval = setInterval(() => fetchTab(activeTab), 10000);
    return () => clearInterval(interval);
  }, [activeTab, fetchTab]);

  const data = tabData[activeTab];

  return (
    <>
      <nav className="tab-bar" aria-label="Dashboard sections">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={activeTab === tab ? 'active' : ''}
          >
            {tab}
          </button>
        ))}
      </nav>

      {error && (
        <div className="error-panel dashboard-error" role="alert">
          <span>{error}</span>
          <button className="btn btn-primary" type="button" onClick={() => fetchTab(activeTab)}>
            Retry
          </button>
        </div>
      )}

      {activeTab === 'Users' ? (
        <div className="dashboard-grid">
          <UserDirectory token={token} onAuthorizationLost={onAuthorizationLost} />
        </div>
      ) : activeTab === 'Audit' ? (
        <div className="dashboard-grid">
          <AuditLog token={token} onAuthorizationLost={onAuthorizationLost} />
        </div>
      ) : loading && !data ? (
        <div className="glass-card loading-card">
          <p className="animate-pulse">Loading {activeTab}…</p>
        </div>
      ) : !data ? (
        <div className="glass-card loading-card">
          <p>No operational data is available for this section.</p>
        </div>
      ) : (
        <div className="dashboard-grid">
          {activeTab === 'Overview' && (
            <>
              <SystemHealth health={data.health} />
              <UserManagement
                users={data.users}
                token={token}
                onAuthorizationLost={onAuthorizationLost}
                onRevoke={() => fetchTab('Overview')}
              />
            </>
          )}
          {activeTab === 'Learning' && <LearningPanel data={data} />}
          {activeTab === 'Roleplay' && <RoleplayPanel data={data} />}
          {activeTab === 'Errors' && <ErrorFeed data={data} />}
        </div>
      )}
    </>
  );
};

export default Dashboard;
