import { StatsCards } from '@/components/dashboard/stats-cards';
import { RecentJobs } from '@/components/dashboard/recent-jobs';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { api } from '@/lib/api/client';

export default async function DashboardPage() {
  const [jobs, apps, runs] = await Promise.all([
    api.getJobs(),
    api.getApplications(),
    api.getLLMRuns(),
  ]);

  const applyCount = jobs.filter(j => j.recommendation === 'apply').length;
  const maybeCount = jobs.filter(j => j.recommendation === 'maybe').length;
  const skipCount = jobs.filter(j => j.recommendation === 'skip').length;
  const avgLatency = runs.length
    ? Math.round(runs.reduce((a, r) => a + r.latency_ms, 0) / runs.length)
    : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">Overview of your job search</p>
      </div>

      <StatsCards
        totalJobs={jobs.length}
        applyCount={applyCount}
        maybeCount={maybeCount}
        skipCount={skipCount}
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
                <span className="font-medium text-emerald-600">{runs.filter(r => r.status === 'success' || r.status === 'completed').length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Failed</span>
                <span className="font-medium text-red-600">{runs.filter(r => r.status === 'error' || r.status === 'failed').length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Avg Latency</span>
                <span className="font-medium text-slate-900">
                  {avgLatency}ms
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
