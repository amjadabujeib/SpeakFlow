import React, { useState } from 'react';

const UserManagement = ({ users, onRevoke }) => {
  const [revoking, setRevoking] = useState(null);

  if (!users) return null;

  const handleRevoke = async (userId) => {
    setRevoking(userId);
    try {
      const response = await fetch(`/admin/users/${userId}/revoke`, { method: 'POST' });
      if (response.ok) {
        if (onRevoke) onRevoke();
      } else {
        alert('Failed to revoke sessions');
      }
    } catch (e) {
      alert('Error revoking sessions: ' + e.message);
    } finally {
      setRevoking(null);
    }
  };

  return (
    <div className="glass-card" style={{ gridColumn: 'span 2' }}>
      <h2>User Management</h2>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        <div>
          <div className="stat-value">{users.total_registered}</div>
          <div className="stat-label">Registered Accounts</div>
        </div>
        <div>
          <div className="stat-value">{users.total_guests}</div>
          <div className="stat-label">Guest Accounts</div>
        </div>
        <div>
          <div className="stat-value" style={{ color: 'var(--secondary-color)' }}>{users.active_sessions}</div>
          <div className="stat-label">Active Sessions</div>
        </div>
      </div>

      <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-secondary)' }}>Recent Registrations</h3>
      
      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Email / Type</th>
              <th>Created At</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.recent_registrations.map(user => (
              <tr key={user.id}>
                <td style={{ fontFamily: 'monospace' }}>{user.id}</td>
                <td>
                  <div>{user.email}</div>
                  <span className={`status-badge ${user.type === 'registered' ? 'healthy' : 'warning'}`} style={{ fontSize: '0.65rem', marginTop: '4px' }}>
                    {user.type}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleString()}</td>
                <td>
                  <button 
                    className="btn btn-danger" 
                    style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                    onClick={() => handleRevoke(user.id)}
                    disabled={revoking === user.id}
                  >
                    {revoking === user.id ? 'Revoking...' : 'Revoke'}
                  </button>
                </td>
              </tr>
            ))}
            {users.recent_registrations.length === 0 && (
              <tr>
                <td colSpan="4" style={{ textAlign: 'center', padding: '2rem' }}>No recent registrations</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default UserManagement;
