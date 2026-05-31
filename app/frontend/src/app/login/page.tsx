'use client';

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [passwordWarning, setPasswordWarning] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setPasswordWarning(false);
    setSubmitting(true);
    try {
      const result = await login(email, password);
      if (result.passwordNeedsReset) {
        setPasswordWarning(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4 py-10">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(59,130,246,0.35),transparent_30%),radial-gradient(circle_at_80%_10%,rgba(16,185,129,0.28),transparent_28%),linear-gradient(135deg,#0f172a_0%,#1e3a8a_48%,#064e3b_100%)]" />
      <div className="absolute -left-24 top-16 h-72 w-72 rounded-full bg-blue-400/20 blur-3xl" />
      <div className="absolute -right-20 bottom-10 h-80 w-80 rounded-full bg-emerald-300/20 blur-3xl" />

      <div className="relative grid w-full max-w-5xl overflow-hidden rounded-3xl border border-white/15 bg-white/10 shadow-2xl backdrop-blur md:grid-cols-[1.1fr_0.9fr]">
        <div className="hidden flex-col justify-between p-10 text-white md:flex">
          <div>
            <div className="mb-8 inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium text-blue-100">
              AI job search for DACH talent
            </div>
            <h1 className="max-w-md text-4xl font-bold leading-tight">
              Match, track, and tailor every application from one workspace.
            </h1>
            <p className="mt-4 max-w-sm text-sm leading-6 text-blue-100">
              Keep saved roles, applied stages, CV generation, and LLM insights synced across web and iOS.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 text-xs text-blue-100">
            <div className="rounded-2xl border border-white/15 bg-white/10 p-4">
              <p className="text-lg font-semibold text-white">DACH</p>
              <p>market focused</p>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/10 p-4">
              <p className="text-lg font-semibold text-white">AI</p>
              <p>matching</p>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/10 p-4">
              <p className="text-lg font-semibold text-white">CV</p>
              <p>tailoring</p>
            </div>
          </div>
        </div>

        <div className="bg-white/95 p-8 shadow-xl md:p-10">
          <div className="mb-8 text-center">
            <h2 className="text-2xl font-bold text-slate-900">dachjob.ai</h2>
            <p className="mt-1 text-sm text-slate-500">Sign in to your account</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}
          {passwordWarning && (
            <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-700">
              Your password does not meet the current security requirements (8+ characters with
              letters, numbers, and a special character).{' '}
              <Link href="/forgot-password" className="font-medium underline hover:text-amber-800">
                Reset your password
              </Link>{' '}
              to continue.
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-700">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-slate-400">
              Must be at least 8 characters with letters, numbers, and a special character.
            </p>
          </div>

          <div className="text-right">
            <Link href="/forgot-password" className="text-sm font-medium text-blue-600 hover:text-blue-500">
              Forgot password?
            </Link>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Don&apos;t have an account?{' '}
            <Link href="/register" className="font-medium text-blue-600 hover:text-blue-500">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
