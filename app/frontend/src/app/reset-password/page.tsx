'use client';

import { useState, FormEvent, useMemo, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

function getPasswordErrors(password: string): string[] {
  const errors: string[] = [];
  if (password.length > 0 && password.length < 8) {
    errors.push('At least 8 characters');
  }
  if (password.length > 0 && !/[a-zA-Z]/.test(password)) {
    errors.push('At least one letter');
  }
  if (password.length > 0 && !/[0-9]/.test(password)) {
    errors.push('At least one number');
  }
  if (password.length > 0 && !/[^a-zA-Z0-9]/.test(password)) {
    errors.push('At least one special character');
  }
  return errors;
}

function ResetPasswordForm() {
  const { resetPassword } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const passwordErrors = useMemo(() => getPasswordErrors(password), [password]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');

    if (!token) {
      setError('Missing reset token. Please request a new password reset link.');
      return;
    }

    const errors = getPasswordErrors(password);
    if (errors.length > 0) {
      setError(errors.join('. ') + '.');
      return;
    }

    setSubmitting(true);
    try {
      await resetPassword(token, password);
      setMessage('Password reset successfully. Redirecting to sign in...');
      setTimeout(() => router.push('/login'), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password reset failed');
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="text-center">
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
          Missing reset token. Please request a new password reset link.
        </div>
        <p className="mt-4 text-sm text-slate-500">
          <Link href="/forgot-password" className="font-medium text-blue-600 hover:text-blue-500">
            Request a reset link
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-600">
          {message}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-slate-700">New password</label>
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <p className="mt-1 text-xs text-slate-400">
          Must be at least 8 characters with letters, numbers, and a special character.
        </p>
        {passwordErrors.length > 0 && (
          <ul className="mt-1 list-inside list-disc text-xs text-amber-600">
            {passwordErrors.map((err) => (
              <li key={err}>{err}</li>
            ))}
          </ul>
        )}
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {submitting ? 'Resetting...' : 'Reset password'}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100">
      <div className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-slate-900">Set new password</h1>
          <p className="mt-1 text-sm text-slate-500">
            Choose a new password for your account.
          </p>
        </div>

        <Suspense fallback={<div className="text-center text-sm text-slate-400">Loading...</div>}>
          <ResetPasswordForm />
        </Suspense>

        <p className="mt-6 text-center text-sm text-slate-500">
          <Link href="/login" className="font-medium text-blue-600 hover:text-blue-500">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
