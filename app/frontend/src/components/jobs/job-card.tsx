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

function statusBadge(status: string) {
  if (status === 'applied') return 'green';
  if (status === 'interview') return 'blue';
  if (status === 'offer') return 'green';
  if (status === 'rejected') return 'red';
  if (status === 'saved') return 'yellow';
  return undefined;
}

function effectiveStatus(job: JobPosting) {
  return job.application_status || (job.saved ? 'saved' : job.status || 'new');
}

function displayStatus(status?: string | null) {
  if (!status) return '';
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function JobCard({ job }: JobCardProps) {
  const status = effectiveStatus(job);
  const statusVariant = statusBadge(status);

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
            <Badge variant={statusVariant || 'default'}>{displayStatus(status)}</Badge>
            <span className="text-xs text-slate-400 hidden sm:inline">
              Added {new Date(job.pipeline_added_at || job.created_at).toLocaleDateString()}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
