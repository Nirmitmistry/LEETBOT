import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

export default function Register() {
  const { register, loading } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState({});

  const validate = () => {
    const e = {};
    if (!form.username.trim()) e.username = 'Username is required';
    else if (form.username.length < 3) e.username = 'Min 3 characters';
    else if (form.username.length > 30) e.username = 'Max 30 characters';

    if (!form.email.trim()) e.email = 'Email is required';
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Invalid email';

    if (!form.password) e.password = 'Password is required';
    else if (form.password.length < 6) e.password = 'Min 6 characters';

    if (form.password !== form.confirmPassword)
      e.confirmPassword = 'Passwords do not match';

    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    try {
      await register(form.email, form.username, form.password);
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
          <span className="code-keyword">class</span> <span className="code-fn">Solution</span>:
        </div>
        <div className="floating-code floating-code--2">
          <span className="code-keyword">if</span> root <span className="code-keyword">is</span> None:
        </div>
        <div className="floating-code floating-code--3">
          stack.<span className="code-fn">append</span>(node)
        </div>
        <div className="floating-code floating-code--4">
          <span className="code-keyword">while</span> queue:
        </div>
        <div className="floating-code floating-code--5">
          memo[key] = result
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
              Start your competitive programming journey.<br />
              AI-guided learning, one problem at a time.
            </p>

            <div className="auth-brand__features">
              <div className="auth-feature">
                <div className="auth-feature__icon">
                  <svg viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd"/></svg>
                </div>
                <div>
                  <h3 className="auth-feature__title">Smart Hints</h3>
                  <p className="auth-feature__desc">AI-powered hints that guide, not spoil</p>
                </div>
              </div>
              <div className="auth-feature">
                <div className="auth-feature__icon">
                  <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z"/></svg>
                </div>
                <div>
                  <h3 className="auth-feature__title">Track Progress</h3>
                  <p className="auth-feature__desc">Monitor your growth across topics</p>
                </div>
              </div>
              <div className="auth-feature">
                <div className="auth-feature__icon">
                  <svg viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.316 3.051a1 1 0 01.633 1.265l-4 12a1 1 0 11-1.898-.632l4-12a1 1 0 011.265-.633zM5.707 6.293a1 1 0 010 1.414L3.414 10l2.293 2.293a1 1 0 11-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0zm8.586 0a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 11-1.414-1.414L16.586 10l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd"/></svg>
                </div>
                <div>
                  <h3 className="auth-feature__title">Complexity Analysis</h3>
                  <p className="auth-feature__desc">Understand time & space trade-offs</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right form panel */}
        <div className="auth-form-panel">
          <div className="auth-form-wrapper">
            <div className="auth-form-header">
              <h2 className="auth-form-title">Create Account</h2>
              <p className="auth-form-subtitle">Join thousands of coders leveling up</p>
            </div>

            <form onSubmit={handleSubmit} className="auth-form" id="register-form">
              <div className="auth-field">
                <label htmlFor="reg-username" className="auth-label">Username</label>
                <div className={`auth-input-wrap ${errors.username ? 'auth-input-wrap--error' : ''}`}>
                  <svg className="auth-input-icon" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                  </svg>
                  <input
                    id="reg-username"
                    type="text"
                    placeholder="leetcoder42"
                    value={form.username}
                    onChange={(e) => setForm({ ...form, username: e.target.value })}
                    className="auth-input"
                    autoComplete="username"
                  />
                </div>
                {errors.username && <span className="auth-error">{errors.username}</span>}
              </div>

              <div className="auth-field">
                <label htmlFor="reg-email" className="auth-label">Email</label>
                <div className={`auth-input-wrap ${errors.email ? 'auth-input-wrap--error' : ''}`}>
                  <svg className="auth-input-icon" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z" />
                    <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z" />
                  </svg>
                  <input
                    id="reg-email"
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
                <label htmlFor="reg-password" className="auth-label">Password</label>
                <div className={`auth-input-wrap ${errors.password ? 'auth-input-wrap--error' : ''}`}>
                  <svg className="auth-input-icon" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                  </svg>
                  <input
                    id="reg-password"
                    type="password"
                    placeholder="••••••••"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="auth-input"
                    autoComplete="new-password"
                  />
                </div>
                {errors.password && <span className="auth-error">{errors.password}</span>}
              </div>

              <div className="auth-field">
                <label htmlFor="reg-confirm" className="auth-label">Confirm Password</label>
                <div className={`auth-input-wrap ${errors.confirmPassword ? 'auth-input-wrap--error' : ''}`}>
                  <svg className="auth-input-icon" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5C18.577 6.374 19 7.929 19 9.375c0 5.279-4.253 9.563-9 10.625-4.747-1.063-9-5.346-9-10.625 0-1.446.423-3.001 1.166-4.376z" clipRule="evenodd" />
                  </svg>
                  <input
                    id="reg-confirm"
                    type="password"
                    placeholder="••••••••"
                    value={form.confirmPassword}
                    onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })}
                    className="auth-input"
                    autoComplete="new-password"
                  />
                </div>
                {errors.confirmPassword && <span className="auth-error">{errors.confirmPassword}</span>}
              </div>

              <button
                type="submit"
                className="auth-submit"
                disabled={loading}
                id="register-submit"
              >
                {loading ? (
                  <span className="auth-spinner" />
                ) : (
                  <>
                    Create Account
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
              Already have an account?{' '}
              <Link to="/login" className="auth-switch__link">
                Sign In
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
