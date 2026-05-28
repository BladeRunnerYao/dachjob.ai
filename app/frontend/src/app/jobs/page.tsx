'use client';

import { useState, useEffect, useCallback, type ChangeEvent } from 'react';
import { JobCard } from '@/components/jobs/job-card';
import { JobForm } from '@/components/jobs/job-form';
import { api } from '@/lib/api/client';
import type { JobPosting } from '@/lib/api/types';

const PAGE_SIZES = [15, 30, 50, 100];

type FilterKey = 'all' | 'apply' | 'maybe' | 'skip';

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(15);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    const result = await api.getJobsPaginated(pageSize, page * pageSize);
    setJobs(result.items);
    setTotal(result.total);
    setLoading(false);
  }, [page, pageSize]);

  useEffect(() => {
    let cancelled = false;

    async function loadJobs() {
      const result = await api.getJobsPaginated(pageSize, page * pageSize);
      if (!cancelled) {
        setJobs(result.items);
        setTotal(result.total);
        setLoading(false);
      }
    }

    void loadJobs();
    return () => {
      cancelled = true;
    };
  }, [page, pageSize]);

  const handleSave = async (urlText: string) => {
    setImporting(true);
    setImportError(null);
    try {
      const result = await api.importJobs(urlText);
      await fetchJobs();
      if (result.errors.length > 0) {
        const errorMessages = result.errors.map(
          (e) => `${e.url}: ${e.error}`
        ).join('\n');
        setImportError(errorMessages);
      } else {
        setShowForm(false);
      }
    } catch (error) {
      setImportError(error instanceof Error ? error.message : 'Could not import jobs');
    } finally {
      setImporting(false);
    }
  };

  const handlePageSizeChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setLoading(true);
    setPageSize(Number(e.target.value));
    setPage(0);
  };

  const goToPage = (nextPage: number | ((current: number) => number)) => {
    setLoading(true);
    setPage(nextPage);
  };

  const filtered = filter === 'all' ? jobs : jobs.filter(j => j.recommendation === filter);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (loading) return <p className="text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Jobs</h1>
          <p className="text-sm text-slate-500 mt-1">{total} job postings</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 shrink-0"
        >
          Add Job
        </button>
      </div>

      <div className="flex gap-2 items-center overflow-x-auto -mx-4 px-4 pb-1">
        {(['all', 'apply', 'maybe', 'skip'] as FilterKey[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
            }`}
          >
            {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
            <span className="ml-1 opacity-60">
              ({f === 'all' ? total : jobs.filter(j => j.recommendation === f).length})
            </span>
          </button>
        ))}
        <select
          value={pageSize}
          onChange={handlePageSizeChange}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs bg-white ml-auto"
        >
          {PAGE_SIZES.map(s => <option key={s} value={s}>{s} / page</option>)}
        </select>
      </div>

      <div className="space-y-2">
        {filtered.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-slate-500 py-8 text-center">No jobs match this filter.</p>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => goToPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1.5 rounded border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
          >
            Previous
          </button>
          {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => (
            <button
              key={i}
              onClick={() => goToPage(i)}
              className={`px-3 py-1.5 rounded border ${i === page ? 'bg-slate-900 text-white border-slate-900' : 'border-slate-300 hover:bg-slate-50'}`}
            >
              {i + 1}
            </button>
          ))}
          <button
            onClick={() => goToPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="px-3 py-1.5 rounded border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
          >
            Next
          </button>
        </div>
      )}

      {showForm && (
        <JobForm
          onClose={() => setShowForm(false)}
          onSave={handleSave}
          saving={importing}
          error={importError}
        />
      )}
    </div>
  );
}
