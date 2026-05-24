'use client';

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';

interface User {
  id: string;
  email: string;
  name: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ passwordNeedsReset?: boolean }>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
  requestPasswordReset: (email: string) => Promise<{ message: string; resetLink?: string; detail?: string }>;
  resetPassword: (token: string, newPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function getApiBase() {
  return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const stored = localStorage.getItem('auth_token');
    if (stored) {
      setToken(stored);
      fetch(`${getApiBase()}/api/auth/me`, {
        headers: { Authorization: `Bearer ${stored}` },
      })
        .then((res) => {
          if (!res.ok) throw new Error('Token invalid');
          return res.json();
        })
        .then((data) => {
          setUser(data);
          setLoading(false);
        })
        .catch(() => {
          localStorage.removeItem('auth_token');
          setToken(null);
          setLoading(false);
          router.push('/login');
        });
    } else {
      setLoading(false);
    }
  }, [router]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${getApiBase()}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Login failed');
    }
    const data = await res.json();
    localStorage.setItem('auth_token', data.token);
    setToken(data.token);
    setUser({ id: data.user_id, email: data.email, name: data.name });
    if (!data.password_needs_reset) {
      router.push('/');
    }
    return { passwordNeedsReset: data.password_needs_reset };
  }, [router]);

  const register = useCallback(async (email: string, password: string, name: string) => {
    const res = await fetch(`${getApiBase()}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
      throw new Error(err.detail || 'Registration failed');
    }
    const data = await res.json();
    localStorage.setItem('auth_token', data.token);
    setToken(data.token);
    setUser({ id: data.user_id, email: data.email, name: data.name });
    router.push('/');
  }, [router]);

  const requestPasswordReset = useCallback(async (email: string) => {
    const res = await fetch(`${getApiBase()}/api/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    return {
      message: data.message || 'If that email is registered, a reset link has been sent.',
      resetLink: data.reset_link || undefined,
    };
  }, []);

  const resetPassword = useCallback(async (token: string, newPassword: string) => {
    const res = await fetch(`${getApiBase()}/api/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password: newPassword }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Password reset failed' }));
      throw new Error(err.detail || 'Password reset failed');
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token');
    setToken(null);
    setUser(null);
    router.push('/login');
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, requestPasswordReset, resetPassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
