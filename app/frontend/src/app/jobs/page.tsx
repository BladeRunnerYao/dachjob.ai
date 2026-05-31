'use client';

import { useState, useEffect, useCallback } from 'react';
import { usePathname } from 'next/navigation';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { JobCard } from '@/components/jobs/job-card';
import { JobForm } from '@/components/jobs/job-form';
import { api } from '@/lib/api/client';
import type { JobPosting } from '@/lib/api/types';
import JobDetailClient from './[id]/job-detail-client';

type FilterKey = 'all' | 'applied' | 'saved';

type JobCounts = Record<FilterKey, number>;

const PAGE_SIZE_OPTIONS = [15, 30, 50, 100] as const;

export default function JobsPage() {
  const pathname = usePathname();
  const routedJobId = pathname.match(/^\/jobs\/([^/?#]+)/)?.[1];
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [counts, setCounts] = useState<JobCounts>({ all: 0, applied: 0, saved: 0 });
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(15);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    if (routedJobId) return;
    setLoading(true);
    const status = filter === 'all' ? undefined : filter;
    const [result, allResult, appliedResult, savedResult] = await Promise.all([
      api.getJobsPaginated(pageSize, page * pageSize, status),
      api.getJobsPaginated(1, 0),
      api.getJobsPaginated(1, 0, 'applied'),
      api.getJobsPaginated(1, 0, 'saved'),
    ]);
    setJobs(result.items);
    setTotal(result.total);
    setCounts({ all: allResult.total, applied: appliedResult.total, saved: savedResult.total });
    setLoading(false);
  }, [filter, page, pageSize, routedJobId]);

  useEffect(() => {
    if (routedJobId) return;
    let cancelled = false;

    async function loadJobs() {
      setLoading(true);
      const status = filter === 'all' ? undefined : filter;
      const [result, allResult, appliedResult, savedResult] = await Promise.all([
        api.getJobsPaginated(pageSize, page * pageSize, status),
        api.getJobsPaginated(1, 0),
        api.getJobsPaginated(1, 0, 'applied'),
        api.getJobsPaginated(1, 0, 'saved'),
      ]);
      if (!cancelled) {
        setJobs(result.items);
        setTotal(result.total);
        setCounts({ all: allResult.total, applied: appliedResult.total, saved: savedResult.total });
        setLoading(false);
      }
    }

    void loadJobs();
    return () => {
      cancelled = true;
    };
  }, [filter, page, pageSize, routedJobId]);

  if (routedJobId) {
    return <JobDetailClient jobId={decodeURIComponent(routedJobId)} />;
  }

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

  const goToPage = (nextPage: number | ((current: number) => number)) => {
    setLoading(true);
    setPage(nextPage);
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const paginationPages = Array.from({ length: Math.min(totalPages, 5) }, (_, index) => {
    const start = Math.min(Math.max(page - 2, 0), Math.max(totalPages - 5, 0));
    return start + index;
  });

  const selectFilter = (nextFilter: FilterKey) => {
    setFilter(nextFilter);
    setPage(0);
  };

  const updatePageSize = (nextPageSize: number) => {
    if (PAGE_SIZE_OPTIONS.includes(nextPageSize as (typeof PAGE_SIZE_OPTIONS)[number])) {
      setPageSize(nextPageSize as (typeof PAGE_SIZE_OPTIONS)[number]);
      setPage(0);
    }
  };

  if (loading) return <p className="text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Jobs</h1>
          <p className="text-sm text-slate-500 mt-1">{counts.all} job postings</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 shrink-0"
        >
          Add Job
        </button>
      </div>

      <div className="flex gap-2 items-center overflow-x-auto -mx-4 px-4 pb-1">
        {(['all', 'applied', 'saved'] as FilterKey[]).map((f) => (
          <button
            key={f}
            onClick={() => selectFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
            }`}
          >
            {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
            <span className="ml-1 opacity-60">
              ({counts[f]})
            </span>
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-500">Jobs per page</span>
          <select
            value={pageSize}
            onChange={(event) => updatePageSize(Number(event.target.value))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center justify-center gap-2 text-sm flex-wrap">
          <button
            onClick={() => goToPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            aria-label="Previous page"
            className="inline-flex h-9 w-9 items-center justify-center rounded border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          {paginationPages.map((pageNumber) => (
            <button
              key={pageNumber}
              onClick={() => goToPage(pageNumber)}
              className={`px-3 py-1.5 rounded border ${pageNumber === page ? 'bg-slate-900 text-white border-slate-900' : 'border-slate-300 hover:bg-slate-50'}`}
            >
              {pageNumber + 1}
            </button>
          ))}
          <button
            onClick={() => goToPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            aria-label="Next page"
            className="inline-flex h-9 w-9 items-center justify-center rounded border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {jobs.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
        {jobs.length === 0 && (
          <p className="text-sm text-slate-500 py-8 text-center">No jobs match this filter.</p>
        )}
      </div>
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
