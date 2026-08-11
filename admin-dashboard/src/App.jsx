import React, { useCallback, useState } from 'react';
import { signOut } from './adminApi';
import AdminLogin from './components/AdminLogin';
import Dashboard from './components/Dashboard';

const SESSION_KEY = 'speakflow_admin_session';

function restoreSession() {
  try {
    const value = JSON.parse(sessionStorage.getItem(SESSION_KEY));
    if (value?.access_token && value?.user?.is_admin === true) return value;
  } catch {
    // Invalid or unavailable browser storage starts a fresh sign-in.
  }
  return null;
}

function App() {
  const [session, setSession] = useState(restoreSession);

  const clearSession = useCallback(() => {
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch {
      // In-memory sign-out still succeeds.
    }
    setSession(null);
  }, []);

  const handleAuthenticated = (nextSession) => {
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
    } catch {
      // The authenticated session remains memory-only when storage is blocked.
    }
    setSession(nextSession);
  };

  const handleSignOut = async () => {
    const token = session?.access_token;
    clearSession();
    if (token) await signOut(token).catch(() => {});
  };

  if (!session) return <AdminLogin onAuthenticated={handleAuthenticated} />;

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div>
          <h1>SpeakFlow Operations</h1>
          <p>Signed in as {session.user.email}</p>
        </div>
        <button className="btn btn-primary" type="button" onClick={handleSignOut}>
          Sign out
        </button>
      </header>
      <Dashboard
        token={session.access_token}
        onAuthorizationLost={clearSession}
      />
    </div>
  );
}

export default App;
