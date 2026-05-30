'use client';

import { useEffect, useState } from 'react';
import { StatsCards } from './stats-cards';
import { RecentJobs } from './recent-jobs';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { api } from '@/lib/api/client';
import type { JobPosting, Application, LLMRun } from '@/lib/api/types';

export function DashboardContent() {
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [appliedCount, setAppliedCount] = useState(0);
  const [savedCount, setSavedCount] = useState(0);
  const [apps, setApps] = useState<Application[]>([]);
  const [runs, setRuns] = useState<LLMRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [jobsData, appliedData, savedData, appsData, runsData] = await Promise.all([
          api.getJobsPaginated(5, 0),
          api.getJobsPaginated(1, 0, 'applied'),
          api.getJobsPaginated(1, 0, 'saved'),
          api.getApplications(),
          api.getLLMRuns({ limit: 200 }),
        ]);
        setJobs(jobsData.items);
        setTotalJobs(jobsData.total);
        setAppliedCount(appliedData.total);
        setSavedCount(savedData.total);
        setApps(appsData);
        setRuns(runsData.items || []);
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
        totalApplications={apps.length}
        totalRuns={runs.length}
      />

      <RecentJobs jobs={jobs} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-900">Recent Applications</h2>
          </CardHeader>
          <CardContent className="space-y-3">
            {apps.slice(0, 3).map((app) => (
              <div key={app.id} className="flex items-center justify-between text-sm">
                <div>
                  <p className="font-medium text-slate-900">{app.job_title}</p>
                  <p className="text-xs text-slate-500">{app.company}</p>
                </div>
                <span className="text-xs text-slate-400 capitalize">{app.status}</span>
              </div>
            ))}
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
                <span className="font-medium text-slate-900">{runs.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Successful</span>
                <span className="font-medium text-emerald-600">
                  {runs.filter((r) => r.status === 'success' || r.status === 'completed').length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Failed</span>
                <span className="font-medium text-red-600">
                  {runs.filter((r) => r.status === 'error' || r.status === 'failed').length}
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
