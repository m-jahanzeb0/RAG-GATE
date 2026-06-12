import { useState } from 'react';
import { KeyRound, ArrowRight, AlertCircle, Cpu } from 'lucide-react';
import { setApiKey, validateApiKey } from '../api/client';

interface AuthGateProps {
  onAuthenticated: () => void;
}

export default function AuthGate({ onAuthenticated }: AuthGateProps) {
  const [key, setKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!key.trim()) return;

    setLoading(true);
    setError('');

    try {
      const valid = await validateApiKey(key.trim());
      if (valid) {
        setApiKey(key.trim());
        onAuthenticated();
      } else {
        setError('Invalid API key. Please check and try again.');
      }
    } catch {
      setError('Could not connect to the gateway. Is the server running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-accent-blue/15 backdrop-blur-xl border border-accent-blue/20 mb-5">
            <Cpu className="w-8 h-8 text-accent-blue" />
          </div>
          <h1 className="text-3xl font-semibold text-white tracking-tight">RAG-Gate</h1>
          <p className="text-gray-400 mt-2">AI Gateway Dashboard</p>
        </div>

        {/* Auth Card */}
        <form onSubmit={handleSubmit} className="glass-card p-8 space-y-5">
          <div className="flex items-center gap-3 text-gray-300">
            <KeyRound className="w-5 h-5 text-accent-blue" />
            <span className="font-medium">Enter your API Key</span>
          </div>

          <input
            type="text"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="rg_test_..."
            className="glass-input w-full font-mono text-sm"
            autoFocus
          />

          {error && (
            <div className="flex items-start gap-2 text-accent-rose text-sm bg-accent-rose/10 border border-accent-rose/20 rounded-xl p-3">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !key.trim()}
            className="glass-button w-full flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin" />
                Verifying...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                Connect <ArrowRight className="w-4 h-4" />
              </span>
            )}
          </button>
        </form>

        <p className="text-center text-xs text-gray-500 mt-6">
          Your API key is stored locally and never sent anywhere except RAG-Gate.
        </p>
      </div>
    </div>
  );
}