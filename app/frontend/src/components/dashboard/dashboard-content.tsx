'use client';

import { useEffect, useState } from 'react';
import { StatsCards } from './stats-cards';
import { RecentJobs } from './recent-jobs';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { api } from '@/lib/api/client';
import type { JobPosting, LLMRun } from '@/lib/api/types';
import Link from 'next/link';

export function DashboardContent() {
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [appliedCount, setAppliedCount] = useState(0);
  const [savedCount, setSavedCount] = useState(0);
  const [recentApplied, setRecentApplied] = useState<JobPosting[]>([]);
  const [runs, setRuns] = useState<LLMRun[]>([]);
  const [runSummary, setRunSummary] = useState({
    total: 0,
    successful: 0,
    failed: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [
          jobsData,
          appliedData,
          savedData,
          recentAppliedData,
          runsData,
          successRuns,
          completedRuns,
          errorRuns,
          failedRuns,
        ] = await Promise.all([
          api.getJobsPaginated(5, 0),
          api.getJobsPaginated(1, 0, 'applied'),
          api.getJobsPaginated(1, 0, 'saved'),
          api.getJobsPaginated(3, 0, 'applied'),
          api.getLLMRuns({ limit: 200 }),
          api.getLLMRuns({ limit: 1, status: 'success' }),
          api.getLLMRuns({ limit: 1, status: 'completed' }),
          api.getLLMRuns({ limit: 1, status: 'error' }),
          api.getLLMRuns({ limit: 1, status: 'failed' }),
        ]);
        setJobs(jobsData.items);
        setTotalJobs(jobsData.total);
        setAppliedCount(appliedData.total);
        setSavedCount(savedData.total);
        setRecentApplied(recentAppliedData.items);
        setRuns(runsData.items || []);
        setRunSummary({
          total: runsData.total,
          successful: successRuns.total + completedRuns.total,
          failed: errorRuns.total + failedRuns.total,
        });
      } catch {
        // In production, leave state as empty if API is unreachable
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const avgLatency = runs.length
    ? Math.round(runs.reduce((a, r) => a + r.latency_ms, 0) / runs.length)
    : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-sm text-slate-500">Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">Overview of your job search</p>
      </div>

      <StatsCards
        totalJobs={totalJobs}
        appliedCount={appliedCount}
        savedCount={savedCount}
        totalRuns={runSummary.total}
      />

      <RecentJobs jobs={jobs} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-900">Recent Applied</h2>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentApplied.map((job) => (
              <div key={job.id} className="flex items-center justify-between text-sm">
                <div>
                  <Link href={`/jobs/${job.id}`} className="font-medium text-slate-900 hover:text-blue-600">
                    {job.title}
                  </Link>
                  <p className="text-xs text-slate-500">{job.company}</p>
                </div>
                <span className="text-xs text-slate-400 capitalize">
                  {job.application_status || 'applied'}
                </span>
              </div>
            ))}
            {recentApplied.length === 0 && (
              <p className="text-sm text-slate-500">No applied jobs yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-900">LLM Run Summary</h2>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-600">Total Runs</span>
                <span className="font-medium text-slate-900">{runSummary.total}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Successful</span>
                <span className="font-medium text-emerald-600">
                  {runSummary.successful}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Failed</span>
                <span className="font-medium text-red-600">
                  {runSummary.failed}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Avg Latency</span>
                <span className="font-medium text-slate-900">{avgLatency}ms</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
