'use client';

import { useState, useEffect, useCallback } from 'react';
import { usePathname } from 'next/navigation';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { JobCard } from '@/components/jobs/job-card';
import { JobForm } from '@/components/jobs/job-form';
import { api } from '@/lib/api/client';
import type { JobFilterOptions, JobPosting, JobQueryOptions, JobStatusFilterValue } from '@/lib/api/types';
import JobDetailClient from './[id]/job-detail-client';

const PAGE_SIZE_OPTIONS = [15, 30, 50, 100] as const;

export default function JobsPage() {
  const pathname = usePathname();
  const routedJobId = pathname.match(/^\/jobs\/([^/?#]+)/)?.[1];
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [companyQueryFilter, setCompanyQueryFilter] = useState('');
  const [addedDateFilter, setAddedDateFilter] = useState('');
  const [countryFilter, setCountryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<JobStatusFilterValue | 'all'>('all');
  const [filterOptions, setFilterOptions] = useState<JobFilterOptions>({
    companies: [],
    statuses: [],
    added_dates: [],
    countries: [],
  });
  const [allCount, setAllCount] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(15);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    if (routedJobId) return;
    setLoading(true);
    const query: JobQueryOptions = {
      status: statusFilter === 'saved' ? statusFilter : undefined,
      stage: statusFilter !== 'all' && statusFilter !== 'saved' ? statusFilter : 'all',
      company_query: companyQueryFilter.trim() || undefined,
      added_date: addedDateFilter || undefined,
      country: countryFilter || undefined,
    };
    const [result, allResult, filtersResult] = await Promise.all([
      api.getJobsPaginated(pageSize, page * pageSize, query),
      api.getJobsPaginated(1, 0),
      api.getJobFilters(),
    ]);
    setJobs(result.items);
    setTotal(result.total);
    setAllCount(allResult.total);
    setFilterOptions(filtersResult);
    setLoading(false);
  }, [addedDateFilter, companyQueryFilter, countryFilter, page, pageSize, routedJobId, statusFilter]);

  useEffect(() => {
    if (routedJobId) return;
    let cancelled = false;

    async function loadJobs() {
      setLoading(true);
      const query: JobQueryOptions = {
        status: statusFilter === 'saved' ? statusFilter : undefined,
        stage: statusFilter !== 'all' && statusFilter !== 'saved' ? statusFilter : 'all',
        company_query: companyQueryFilter.trim() || undefined,
        added_date: addedDateFilter || undefined,
        country: countryFilter || undefined,
      };
      const [result, allResult, filtersResult] = await Promise.all([
        api.getJobsPaginated(pageSize, page * pageSize, query),
        api.getJobsPaginated(1, 0),
        api.getJobFilters(),
      ]);
      if (!cancelled) {
        setJobs(result.items);
        setTotal(result.total);
        setAllCount(allResult.total);
        setFilterOptions(filtersResult);
        setLoading(false);
      }
    }

    void loadJobs();
    return () => {
      cancelled = true;
    };
  }, [addedDateFilter, companyQueryFilter, countryFilter, page, pageSize, routedJobId, statusFilter]);

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

  const clearStatusFilter = () => {
    setStatusFilter('all');
    setPage(0);
  };

  const updateCompanyQueryFilter = (companyQuery: string) => {
    setCompanyQueryFilter(companyQuery);
    setPage(0);
  };

  const updateAddedDateFilter = (addedDate: string) => {
    setAddedDateFilter(addedDate);
    setPage(0);
  };

  const updateCountryFilter = (country: string) => {
    setCountryFilter(country);
    setPage(0);
  };

  const updateStatusFilter = (status: JobStatusFilterValue | 'all') => {
    setStatusFilter(status);
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
          <p className="text-sm text-slate-500 mt-1">{allCount} job postings</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 shrink-0"
        >
          Add Job
        </button>
      </div>

      <div className="flex flex-col gap-3 text-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={clearStatusFilter}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              statusFilter === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
            }`}
          >
            All
            <span className="ml-1 opacity-60">({allCount})</span>
          </button>
          <input
            type="search"
            value={companyQueryFilter}
            onChange={(event) => updateCompanyQueryFilter(event.target.value)}
            list="company-filter-options"
            placeholder="Company"
            aria-label="Company filter"
            className="w-[180px] rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <datalist id="company-filter-options">
            {filterOptions.companies.map((company) => (
              <option key={company.value} value={company.value}>
                {`${company.value} (${company.count})`}
              </option>
            ))}
          </datalist>
          <select
            value={addedDateFilter}
            onChange={(event) => updateAddedDateFilter(event.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All added dates</option>
            {filterOptions.added_dates.map((addedDate) => (
              <option key={addedDate.value} value={addedDate.value}>
                {new Date(`${addedDate.value}T00:00:00`).toLocaleDateString()} ({addedDate.count})
              </option>
            ))}
          </select>
          <select
            value={countryFilter}
            onChange={(event) => updateCountryFilter(event.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All countries</option>
            {filterOptions.countries.map((country) => (
              <option key={country.value} value={country.value}>
                {country.value} ({country.count})
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(event) => updateStatusFilter(event.target.value as JobStatusFilterValue | 'all')}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All statuses</option>
            {filterOptions.statuses.map((status) => (
              <option key={status.value} value={status.value}>
                {status.value.charAt(0).toUpperCase() + status.value.slice(1)} ({status.count})
              </option>
            ))}
          </select>
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
