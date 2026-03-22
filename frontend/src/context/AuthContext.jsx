import { createContext, useContext, useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';

const AuthContext = createContext(null);

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

export function AppProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('leetbot_token'));
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('leetbot_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(false);

  // Keep axios header in sync with token
  useEffect(() => {
    if (token) {
      API.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete API.defaults.headers.common['Authorization'];
    }
  }, [token]);

  const login = async (email, password) => {
    setLoading(true);
    try {
      const { data } = await API.post('/auth/login', { email, password });
      setToken(data.access_token);
      setUser(data.user);
      localStorage.setItem('leetbot_token', data.access_token);
      localStorage.setItem('leetbot_user', JSON.stringify(data.user));
      toast.success('Welcome back!');
      return data;
    } catch (err) {
      const msg = err.response?.data?.detail || 'Login failed';
      toast.error(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const register = async (email, username, password) => {
    setLoading(true);
    try {
      const { data } = await API.post('/auth/register', { email, username, password });
      setToken(data.access_token);
      setUser(data.user);
      localStorage.setItem('leetbot_token', data.access_token);
      localStorage.setItem('leetbot_user', JSON.stringify(data.user));
      toast.success('Account created successfully!');
      return data;
    } catch (err) {
      const msg = err.response?.data?.detail || 'Registration failed';
      toast.error(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('leetbot_token');
    localStorage.removeItem('leetbot_user');
    toast.success('Logged out');
  };

  const value = useMemo(
    () => ({ user, token, loading, login, register, logout, API }),
    [user, token, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AppProvider');
  return ctx;
}

export default AuthContext;