import { Card } from '@/components/ui/card';

interface StatsCardsProps {
  totalJobs: number;
  appliedCount: number;
  savedCount: number;
  totalApplications: number;
  totalRuns: number;
}

export function StatsCards({ totalJobs, appliedCount, savedCount, totalApplications, totalRuns }: StatsCardsProps) {
  const stats = [
    { label: 'Total Jobs', value: totalJobs, color: 'text-blue-600' },
    { label: 'Applied', value: appliedCount, color: 'text-emerald-600' },
    { label: 'Saved', value: savedCount, color: 'text-amber-600' },
    { label: 'Applications', value: totalApplications, color: 'text-indigo-600' },
    { label: 'LLM Runs', value: totalRuns, color: 'text-purple-600' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {stats.map((stat) => (
        <Card key={stat.label} className="px-4 py-3">
          <p className="text-sm text-slate-500">{stat.label}</p>
          <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
        </Card>
      ))}
    </div>
  );
}
