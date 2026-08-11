import React, { useState } from 'react';
import { signIn } from '../adminApi';

const AdminLogin = ({ onAuthenticated }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      onAuthenticated(await signIn(email.trim(), password));
    } catch (requestError) {
      setError(requestError.message || 'Sign-in failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-shell">
      <form className="glass-card login-card" onSubmit={handleSubmit}>
        <h1>SpeakFlow Operations</h1>
        <h2>Administrator sign in</h2>
        <p>Use a registered account that was granted administrator access.</p>
        <label htmlFor="admin-email">Email</label>
        <input
          id="admin-email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <label htmlFor="admin-password">Password</label>
        <input
          id="admin-password"
          type="password"
          autoComplete="current-password"
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {error && <div className="error-panel" role="alert">{error}</div>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  );
};

export default AdminLogin;
