import { createContext, useContext, useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';

const AuthContext = createContext(null);

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

API.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('leetbot_token');
      localStorage.removeItem('leetbot_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export function AppProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('leetbot_token'));
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('leetbot_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const validateToken = async () => {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        API.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        const { data } = await API.get('/users/me');
        setUser(data);
        localStorage.setItem('leetbot_user', JSON.stringify(data));
      } catch {
        // Token is invalid/expired — clear everything
        setToken(null);
        setUser(null);
        localStorage.removeItem('leetbot_token');
        localStorage.removeItem('leetbot_user');
      } finally {
        setLoading(false);
      }
    };
    validateToken();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const refreshUser = async () => {
    try {
      const { data } = await API.get('/users/me');
      setUser(data);
      localStorage.setItem('leetbot_user', JSON.stringify(data));
      return data;
    } catch (err) {
      console.error('Failed to refresh user', err);
    }
  };

  const value = useMemo(
    () => ({ user, setUser, token, loading, login, register, logout, refreshUser, API }),
    [user, token, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AppProvider');
  return ctx;
}

export default AuthContext;