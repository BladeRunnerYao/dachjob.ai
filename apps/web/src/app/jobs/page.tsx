'use client';

import { useState, useEffect } from 'react';
import { JobCard } from '@/components/jobs/job-card';
import { JobForm } from '@/components/jobs/job-form';
import { api } from '@/lib/api/client';
import type { JobPosting } from '@/lib/api/types';

type FilterKey = 'all' | 'apply' | 'maybe' | 'skip';

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [filter, setFilter] = useState<FilterKey>('all');

  useEffect(() => {
    api.getJobs().then((data) => {
      setJobs(data);
      setLoading(false);
    });
  }, []);

  const handleSave = (jd: string) => {
    const newJob: JobPosting = {
      id: String(Date.now()),
      title: 'New Job',
      company: 'Unknown',
      status: 'active',
      score: 0,
      recommendation: 'maybe',
      raw_jd: jd,
      created_at: new Date().toISOString(),
    };
    setJobs([newJob, ...jobs]);
    setShowForm(false);
  };

  const filtered = filter === 'all' ? jobs : jobs.filter(j => j.recommendation === filter);

  if (loading) return <p className="text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Jobs</h1>
          <p className="text-sm text-slate-500 mt-1">{jobs.length} job postings</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
        >
          Add Job
        </button>
      </div>

      <div className="flex gap-2">
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
              ({f === 'all' ? jobs.length : jobs.filter(j => j.recommendation === f).length})
            </span>
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {filtered.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-slate-500 py-8 text-center">No jobs match this filter.</p>
        )}
      </div>

      {showForm && <JobForm onClose={() => setShowForm(false)} onSave={handleSave} />}
    </div>
  );
}
