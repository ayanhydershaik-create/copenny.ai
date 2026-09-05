import React, { useState } from 'react';
import { X, Mail, Lock, User, Eye, EyeOff, Chrome, ArrowRight } from 'lucide-react';
import { signInWithGoogle, signInWithEmail, registerWithEmail, activateDemoMode } from '../lib/firebase';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultTab?: 'login' | 'register';
  onSuccess?: (uid: string) => void;
}

const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, defaultTab = 'login', onSuccess }) => {
  const [tab, setTab] = useState<'login' | 'register'>(defaultTab);
  const [email, setEmail] = useState('');

  React.useEffect(() => {
    if (isOpen) {
      setTab(defaultTab);
    }
  }, [defaultTab, isOpen]);
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const redirectToDashboard = () => {
    window.location.href = '/ui';
  };

  const handleActionSuccess = (uid: string) => {
    if (onSuccess) {
      onSuccess(uid);
    } else {
      redirectToDashboard();
    }
  };

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setError('');
    const { user, error: err } = await signInWithGoogle();
    setLoading(false);
    if (user) handleActionSuccess(user.uid);
    else setError(err || 'Google sign-in failed');
  };

  const handleDemoMode = async () => {
    setLoading(true);
    setError('');
    const ok = await activateDemoMode();
    const uid = localStorage.getItem('copenny_user_id') || 'demo_user';
    setLoading(false);
    if (ok) handleActionSuccess(uid);
    else setError('Demo mode unavailable. Please try again.');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!email || !password) { setError('Please fill in all fields.'); return; }
    if (tab === 'register' && !name) { setError('Please enter your name.'); return; }

    setLoading(true);
    const result = tab === 'login'
      ? await signInWithEmail(email, password)
      : await registerWithEmail(email, password, name);
    setLoading(false);

    if (result.user) handleActionSuccess(result.user.uid);
    else setError(result.error || 'Authentication failed');
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      
      {/* Modal */}
      <div
        className="relative w-full max-w-md mx-4 rounded-[32px] border border-white/10 shadow-2xl overflow-hidden"
        style={{ background: 'rgba(9,11,20,0.97)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Top Glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-32 bg-cyan-400/10 blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="relative p-8 pb-0 flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-black text-white tracking-tight">
              {tab === 'login' ? 'Welcome back 👋' : 'Create account'}
            </h2>
            <p className="text-sm text-slate-500 mt-1">
              {tab === 'login' ? 'Sign in to your Co Penny dashboard' : 'Start your AI finance journey'}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors p-1">
            <X size={20} />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="relative px-8 pt-6">
          <div className="flex p-1 rounded-2xl bg-white/5 border border-white/5">
            {(['login', 'register'] as const).map(t => (
              <button
                key={t}
                onClick={() => { setTab(t); setError(''); }}
                className={`flex-1 py-2.5 rounded-xl text-sm font-bold transition-all ${
                  tab === t
                    ? 'bg-white text-black shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {t === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="relative p-8 space-y-4">
          {tab === 'register' && (
            <div className="relative">
              <User size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Full Name"
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full pl-11 pr-4 py-3.5 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-400/50 focus:bg-white/8 transition-all"
              />
            </div>
          )}

          <div className="relative">
            <Mail size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="email"
              placeholder="Email address"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full pl-11 pr-4 py-3.5 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-400/50 transition-all"
            />
          </div>

          <div className="relative">
            <Lock size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type={showPass ? 'text' : 'password'}
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full pl-11 pr-11 py-3.5 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-400/50 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowPass(!showPass)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors"
            >
              {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-4 rounded-2xl text-sm font-black uppercase tracking-widest transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            style={{
              background: 'linear-gradient(135deg, #00FFFF 0%, #0088FF 100%)',
              color: '#000',
              boxShadow: '0 0 24px rgba(0,255,255,0.3)'
            }}
          >
            {loading ? (
              <span className="animate-spin inline-block w-4 h-4 border-2 border-black/30 border-t-black rounded-full" />
            ) : (
              <>
                {tab === 'login' ? 'Sign In' : 'Create Account'}
                <ArrowRight size={16} />
              </>
            )}
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-xs text-slate-600 font-bold uppercase tracking-wider">or</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Google Sign In */}
          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={loading}
            className="w-full py-3.5 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 text-white text-sm font-bold flex items-center justify-center gap-3 transition-all disabled:opacity-50"
          >
            <Chrome size={18} className="text-blue-400" />
            Continue with Google
          </button>

          {/* Demo Mode */}
          <button
            type="button"
            onClick={handleDemoMode}
            disabled={loading}
            className="w-full py-3 rounded-2xl border border-emerald-500/20 text-emerald-400 text-xs font-black uppercase tracking-widest hover:bg-emerald-500/10 transition-all disabled:opacity-50"
          >
            🎬 Try Demo Mode (No signup needed)
          </button>
        </form>

        {/* Footer */}
        <div className="px-8 pb-6 text-center text-[10px] text-slate-600 uppercase tracking-widest font-bold">
          CoPenny AI • All rights reserved
        </div>
      </div>
    </div>
  );
};

export default AuthModal;
