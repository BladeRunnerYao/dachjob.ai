'use client';

import { useState, useEffect } from 'react';
import { TrackerTable } from '@/components/tracker/tracker-table';
import { api } from '@/lib/api/client';
import type { Application } from '@/lib/api/types';

const statusFilters = ['saved', 'applied', 'interview', 'rejected', 'offer'];

export default function TrackerPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [selectedStatus, setSelectedStatus] = useState<string>('saved');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getApplications(selectedStatus).then((data) => {
      setApplications(data);
    }).catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load applications');
    }).finally(() => {
      setLoading(false);
    });
  }, [selectedStatus]);

  const handleStatusChange = async (id: string, status: string) => {
    setError(null);
    try {
      const updated = await api.updateApplication(id, { status });
      setApplications((prev) =>
        prev
          .map((app) => (app.id === id ? { ...app, ...updated } : app))
          .filter((app) => app.status.toLowerCase() === selectedStatus)
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update application status');
    }
  };

  const selectStatus = (status: string) => {
    if (status === selectedStatus) return;
    setLoading(true);
    setApplications([]);
    setError(null);
    setSelectedStatus(status);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Application Tracker</h1>
          <p className="text-sm text-slate-500 mt-1">{applications.length} applications tracked</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {statusFilters.map((status) => (
          <button
            key={status}
            onClick={() => selectStatus(status)}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium transition ${
              selectedStatus === status
                ? 'border-blue-600 bg-blue-600 text-white'
                : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-sm text-slate-500">Loading...</p>
      ) : (
        <TrackerTable applications={applications} onStatusChange={handleStatusChange} />
      )}
    </div>
  );
}
