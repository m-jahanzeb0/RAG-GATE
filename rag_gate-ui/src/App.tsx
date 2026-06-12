import { useState, useEffect } from 'react';
import { hasApiKey } from './api/client';
import AuthGate from './components/AuthGate';
import Dashboard from './components/Dashboard';

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    setAuthenticated(hasApiKey());
    setInitialized(true);
  }, []);

  if (!initialized) {
    return null;
  }

  if (!authenticated) {
    return <AuthGate onAuthenticated={() => setAuthenticated(true)} />;
  }

  return <Dashboard onLogout={() => setAuthenticated(false)} />;
}