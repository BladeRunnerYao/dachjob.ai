import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { JobPosting } from '@/lib/api/types';
import Link from 'next/link';

interface JobCardProps {
  job: JobPosting;
}

function toPercent(score: number): number {
  return Math.round((Math.min(Math.max(score, 1), 5) / 5) * 100);
}

function scoreBadge(percent: number) {
  if (percent >= 84) return 'green';
  if (percent >= 72) return 'yellow';
  return 'red';
}

function recBadge(rec: string) {
  if (rec === 'apply') return 'green';
  if (rec === 'maybe') return 'yellow';
  return 'red';
}

export function JobCard({ job }: JobCardProps) {
  return (
    <Link href={`/jobs/${job.id}`}>
      <Card className="hover:border-blue-300 transition-colors cursor-pointer">
        <CardContent className="flex items-center justify-between py-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-slate-900 truncate">{job.title}</p>
            <p className="text-xs text-slate-500">{job.company}{job.location ? ` · ${job.location}` : ''}</p>
          </div>
          <div className="flex items-center gap-2 ml-4 shrink-0">
            {job.score != null && <Badge variant={scoreBadge(toPercent(job.score))}>{toPercent(job.score)}%</Badge>}
            {job.recommendation && <Badge variant={recBadge(job.recommendation)}>{job.recommendation}</Badge>}
            <span className="text-xs text-slate-400 hidden sm:inline">{new Date(job.created_at).toLocaleDateString()}</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
