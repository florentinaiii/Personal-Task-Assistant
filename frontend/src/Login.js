import React, { useState } from 'react';
import { Mail, Lock, ArrowRight } from 'lucide-react';
import LoginRobot from './assets/LoginRobot.png';

const API_URL =
  process.env.REACT_APP_API_URL || 'http://localhost:8001';

const Login = ({ onLogin }) => {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const endpoint = mode === 'login' ? '/login' : '/register';

      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || 'Authentication failed');
      }

      localStorage.setItem('user', JSON.stringify(data.user));
      localStorage.setItem('accessToken', data.access_token);
      onLogin(data.user);
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen w-full flex items-center justify-center overflow-hidden relative px-5"
      style={{
        background:
          'linear-gradient(135deg, #FCFAFF 0%, #F5EFFF 50%, #FBF8FF 100%)',
      }}
    >
      <div
        className="absolute pointer-events-none rounded-full"
        style={{
          width: '720px',
          height: '720px',
          left: '50%',
          top: '50%',
          transform: 'translate(-50%, -50%)',
          background:
            'radial-gradient(circle, rgba(190,150,255,0.17) 0%, rgba(190,150,255,0.05) 48%, transparent 72%)',
        }}
      />

      <div className="relative z-10 w-full max-w-[440px] flex flex-col items-center justify-center">
        <div className="w-full flex justify-center items-end mb-[-14px] relative z-20">
          <img
            src={LoginRobot}
            alt="AI Task Assistant"
            className="block w-[275px] sm:w-[290px] h-auto object-contain pointer-events-none"
            style={{
              filter:
                'drop-shadow(0 10px 20px rgba(124,43,209,0.08))',
            }}
          />
        </div>

        <div
          className="w-full bg-white rounded-[22px] px-8 sm:px-9 py-9 relative z-10"
          style={{
            border: '1px solid rgba(220,201,255,0.95)',
            boxShadow: '0 24px 60px rgba(88,45,140,0.11)',
          }}
        >
          <div className="text-center mb-7">
            <h1
              className="text-[25px] sm:text-[27px] leading-tight font-bold mb-2"
              style={{ color: '#17143D' }}
            >
              AI Task Assistant
            </h1>
            <p className="text-[13px] sm:text-[14px]" style={{ color: '#706B92' }}>
              {mode === 'login'
                ? 'Sign in to your account'
                : 'Create your account'}
            </p>
          </div>

          <form onSubmit={handleSubmit}>
            <div
              className="w-full h-[50px] flex items-center rounded-[11px] px-4 bg-white"
              style={{ border: '1.2px solid #DCC9FF' }}
            >
              <Mail className="w-[17px] h-[17px] flex-shrink-0 mr-3" style={{ color: '#8B2BE2' }} />
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                className="w-full h-full bg-transparent outline-none border-none text-[13px]"
                style={{ color: '#17143D' }}
              />
            </div>

            <div
              className="mt-3 w-full h-[50px] flex items-center rounded-[11px] px-4 bg-white"
              style={{ border: '1.2px solid #DCC9FF' }}
            >
              <Lock className="w-[17px] h-[17px] flex-shrink-0 mr-3" style={{ color: '#8B2BE2' }} />
              <input
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password (minimum 8 characters)"
                className="w-full h-full bg-transparent outline-none border-none text-[13px]"
                style={{ color: '#17143D' }}
              />
            </div>

            {error && (
              <div className="text-red-500 text-[11px] mt-2">{error}</div>
            )}

            <button
              type="submit"
              disabled={isLoading || !email || password.length < 8}
              className="mt-4 w-full h-[50px] rounded-[11px] text-white font-semibold text-[13px] flex items-center justify-center gap-2 transition-all duration-200 hover:opacity-95 hover:scale-[1.01] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
              style={{
                background:
                  'linear-gradient(90deg, #C96AF4 0%, #A466E6 48%, #8C6BE8 100%)',
                boxShadow: '0 9px 20px rgba(124,43,209,0.14)',
              }}
            >
              <span>
                {isLoading
                  ? 'Please wait...'
                  : mode === 'login'
                  ? 'Sign in'
                  : 'Create account'}
              </span>
              {!isLoading && <ArrowRight className="w-[16px] h-[16px]" />}
            </button>
          </form>

          <button
            type="button"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login');
              setError('');
            }}
            className="mt-4 w-full text-[12px] font-medium"
            style={{ color: '#8B2BE2' }}
          >
            {mode === 'login'
              ? "Don't have an account? Create one"
              : 'Already have an account? Sign in'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Login;
