'use client';

import { useState, useEffect } from 'react';
import { TrackerTable } from '@/components/tracker/tracker-table';
import { api } from '@/lib/api/client';
import type { Application } from '@/lib/api/types';

export default function TrackerPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getApplications().then((data) => {
      setApplications(data);
      setLoading(false);
    });
  }, []);

  const handleStatusChange = async (id: string, status: string) => {
    setError(null);
    try {
      const updated = await api.updateApplication(id, { status });
      setApplications((prev) =>
        prev.map((app) => (app.id === id ? { ...app, ...updated } : app))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update application status');
    }
  };

  if (loading) return <p className="text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Application Tracker</h1>
          <p className="text-sm text-slate-500 mt-1">{applications.length} applications tracked</p>
        </div>
      </div>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      <TrackerTable applications={applications} onStatusChange={handleStatusChange} />
    </div>
  );
}
