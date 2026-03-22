import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

export default function Login() {
  const { login, loading } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ email: '', password: '' });
  const [errors, setErrors] = useState({});

  const validate = () => {
    const e = {};
    if (!form.email.trim()) e.email = 'Email is required';
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Invalid email';
    if (!form.password) e.password = 'Password is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    try {
      await login(form.email, form.password);
      navigate('/');
    } catch {
      // error handled in context via toast
    }
  };

  return (
    <div className="auth-page">
      {/* Animated background particles */}
      <div className="auth-bg">
        <div className="auth-grid" />
        <div className="auth-glow auth-glow--1" />
        <div className="auth-glow auth-glow--2" />
        <div className="auth-glow auth-glow--3" />
        {/* Floating code snippets */}
        <div className="floating-code floating-code--1">
          <span className="code-keyword">def</span> <span className="code-fn">twoSum</span>(nums, target):
        </div>
        <div className="floating-code floating-code--2">
          <span className="code-keyword">for</span> i <span className="code-keyword">in</span> range(n):
        </div>
        <div className="floating-code floating-code--3">
          <span className="code-keyword">return</span> dp[n]
        </div>
        <div className="floating-code floating-code--4">
          left, right = <span className="code-num">0</span>, len(s)
        </div>
        <div className="floating-code floating-code--5">
          node = node.<span className="code-fn">next</span>
        </div>
      </div>

      <div className="auth-container">
        {/* Left branding panel */}
        <div className="auth-brand">
          <div className="auth-brand__inner">
            <div className="auth-logo">
              <div className="auth-logo__icon">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M16.102 17.93l-2.697 2.607c-.466.467-1.111.662-1.823.662s-1.357-.195-1.824-.662l-4.332-4.363c-.467-.467-.702-1.15-.702-1.863s.235-1.357.702-1.824l4.319-4.38c.467-.467 1.125-.645 1.837-.645s1.357.195 1.823.662l2.697 2.606c.514.515 1.365.497 1.9-.038.535-.536.553-1.387.038-1.901l-2.609-2.636a5.055 5.055 0 00-3.849-1.593 5.073 5.073 0 00-3.849 1.593l-4.306 4.38C1.112 12.97.9 13.627.9 14.337s.195 1.394.662 1.86l4.332 4.364c1.07 1.07 2.496 1.593 3.849 1.593s2.779-.523 3.849-1.593l2.697-2.607c.514-.514.496-1.365-.039-1.9s-1.386-.553-1.9-.039l-.248-.085z" fill="#FFA116"/>
                  <path d="M20.437 11.662l-4.332-4.363c-1.07-1.07-2.496-1.593-3.849-1.593s-2.779.523-3.849 1.593L5.71 9.906c-.515.514-.497 1.365.038 1.9s1.387.553 1.9.038l2.697-2.607c.467-.467 1.111-.662 1.823-.662s1.357.195 1.824.662l4.332 4.363c.467.467.702 1.15.702 1.863s-.235 1.357-.702 1.824l-4.319 4.38c-.467.467-1.125.645-1.837.645s-1.357-.195-1.823-.662l-2.697-2.606c-.514-.515-1.365-.497-1.9.038-.536.536-.553 1.387-.039 1.901l2.609 2.636a5.055 5.055 0 003.849 1.593 5.073 5.073 0 003.849-1.593l4.306-4.38c.467-.466.679-1.122.679-1.832s-.195-1.394-.662-1.86z" fill="#B3B3B3"/>
                </svg>
              </div>
              <h1 className="auth-logo__text">
                <span className="auth-logo__leet">Leet</span>
                <span className="auth-logo__bot">Bot</span>
              </h1>
            </div>

            <p className="auth-brand__tagline">
              Your AI-powered coding companion.<br />
              Master algorithms. Ace interviews.
            </p>

            <div className="auth-brand__stats">
              <div className="auth-stat">
                <span className="auth-stat__number">2800+</span>
                <span className="auth-stat__label">Problems</span>
              </div>
              <div className="auth-stat">
                <span className="auth-stat__number">AI</span>
                <span className="auth-stat__label">Powered Hints</span>
              </div>
              <div className="auth-stat">
                <span className="auth-stat__number">∞</span>
                <span className="auth-stat__label">Practice</span>
              </div>
            </div>

            <div className="auth-brand__terminal">
              <div className="terminal-bar">
                <span className="terminal-dot terminal-dot--red" />
                <span className="terminal-dot terminal-dot--yellow" />
                <span className="terminal-dot terminal-dot--green" />
              </div>
              <div className="terminal-body">
                <div className="terminal-line">
                  <span className="terminal-prompt">$</span>
                  <span className="terminal-text typing-animation">leetbot solve --hint "Two Sum"</span>
                </div>
                <div className="terminal-line terminal-line--output">
                  <span className="terminal-output">✓ Use a hash map for O(n) time complexity</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right form panel */}
        <div className="auth-form-panel">
          <div className="auth-form-wrapper">
            <div className="auth-form-header">
              <h2 className="auth-form-title">Welcome Back</h2>
              <p className="auth-form-subtitle">Sign in to continue your coding journey</p>
            </div>

            <form onSubmit={handleSubmit} className="auth-form" id="login-form">
              <div className="auth-field">
                <label htmlFor="login-email" className="auth-label">Email</label>
                <div className={`auth-input-wrap ${errors.email ? 'auth-input-wrap--error' : ''}`}>
                  <svg className="auth-input-icon" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z" />
                    <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z" />
                  </svg>
                  <input
                    id="login-email"
                    type="email"
                    placeholder="you@example.com"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="auth-input"
                    autoComplete="email"
                  />
                </div>
                {errors.email && <span className="auth-error">{errors.email}</span>}
              </div>

              <div className="auth-field">
                <label htmlFor="login-password" className="auth-label">Password</label>
                <div className={`auth-input-wrap ${errors.password ? 'auth-input-wrap--error' : ''}`}>
                  <svg className="auth-input-icon" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                  </svg>
                  <input
                    id="login-password"
                    type="password"
                    placeholder="••••••••"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="auth-input"
                    autoComplete="current-password"
                  />
                </div>
                {errors.password && <span className="auth-error">{errors.password}</span>}
              </div>

              <button
                type="submit"
                className="auth-submit"
                disabled={loading}
                id="login-submit"
              >
                {loading ? (
                  <span className="auth-spinner" />
                ) : (
                  <>
                    Sign In
                    <svg className="auth-submit-arrow" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </>
                )}
              </button>
            </form>

            <div className="auth-divider">
              <span>or</span>
            </div>

            <p className="auth-switch">
              Don't have an account?{' '}
              <Link to="/register" className="auth-switch__link">
                Create Account
                <svg className="auth-switch__arrow" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
