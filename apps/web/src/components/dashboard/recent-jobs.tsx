import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { JobPosting } from '@/lib/api/types';
import Link from 'next/link';

interface RecentJobsProps {
  jobs: JobPosting[];
}

function scoreBadge(score: number) {
  if (score >= 4.2) return 'green';
  if (score >= 3.6) return 'yellow';
  return 'red';
}

function recBadge(rec: string) {
  if (rec === 'apply') return 'green';
  if (rec === 'maybe') return 'yellow';
  return 'red';
}

export function RecentJobs({ jobs }: RecentJobsProps) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-sm font-semibold text-slate-900">Recent Jobs</h2>
      </CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className="px-4 py-2 font-medium">Title</th>
              <th className="px-4 py-2 font-medium">Company</th>
              <th className="px-4 py-2 font-medium">Score</th>
              <th className="px-4 py-2 font-medium">Rec.</th>
              <th className="px-4 py-2 font-medium">Date</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2.5">
                  <Link href={`/jobs/${job.id}`} className="font-medium text-slate-900 hover:text-blue-600">
                    {job.title}
                  </Link>
                </td>
                <td className="px-4 py-2.5 text-slate-600">{job.company}</td>
                <td className="px-4 py-2.5">
                  {job.score == null ? (
                    <span className="text-xs text-slate-400">Pending</span>
                  ) : (
                    <Badge variant={scoreBadge(job.score)}>{job.score}</Badge>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  {job.recommendation ? (
                    <Badge variant={recBadge(job.recommendation)}>{job.recommendation}</Badge>
                  ) : (
                    <span className="text-xs text-slate-400">Pending</span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-slate-500">{new Date(job.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
