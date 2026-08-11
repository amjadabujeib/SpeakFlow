import React, { useState } from 'react';
import { revokeSessions } from '../adminApi';

const UserManagement = ({ users, token, onAuthorizationLost, onRevoke }) => {
  const [revoking, setRevoking] = useState(null);

  if (!users) return null;

  const handleRevoke = async (user) => {
    const reason = window.prompt(
      `Why should all active sessions for ${user.email} be revoked?`,
    )?.trim();
    if (!reason) return;
    if (reason.length < 3 || reason.length > 200) {
      window.alert('Enter a reason between 3 and 200 characters.');
      return;
    }
    if (!window.confirm(
      `Revoke every active session for ${user.email}? This will sign the user out on all devices.`,
    )) return;

    setRevoking(user.id);
    try {
      const result = await revokeSessions(user.id, reason, token);
      window.alert(
        `Revoked ${result.revoked_count} session(s). Audit event: ${result.audit_event_id}`,
      );
      onRevoke?.();
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        onAuthorizationLost();
      } else {
        window.alert(error.message || 'Session revocation failed.');
      }
    } finally {
      setRevoking(null);
    }
  };

  return (
    <div className="glass-card" style={{ gridColumn: 'span 2' }}>
      <h2>User Management</h2>

      <div className="user-stats">
        <div>
          <div className="stat-value">{users.total_registered}</div>
          <div className="stat-label">Registered Accounts</div>
        </div>
        <div>
          <div className="stat-value">{users.total_guests}</div>
          <div className="stat-label">Guest Accounts</div>
        </div>
        <div>
          <div className="stat-value accent-stat">{users.active_sessions}</div>
          <div className="stat-label">Active Sessions</div>
        </div>
      </div>

      <h3 className="section-label">Recent Registrations</h3>
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
            {users.recent_registrations.map((user) => (
              <tr key={user.id}>
                <td className="monospace-cell">{user.id}</td>
                <td>
                  <div>{user.email}</div>
                  <span
                    className={`status-badge ${user.type === 'registered' ? 'healthy' : 'warning'}`}
                  >
                    {user.type}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleString()}</td>
                <td>
                  <button
                    className="btn btn-danger"
                    type="button"
                    onClick={() => handleRevoke(user)}
                    disabled={revoking === user.id}
                  >
                    {revoking === user.id ? 'Revoking…' : 'Revoke sessions'}
                  </button>
                </td>
              </tr>
            ))}
            {users.recent_registrations.length === 0 && (
              <tr>
                <td colSpan="4" className="empty-cell">No recent registrations</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default UserManagement;
