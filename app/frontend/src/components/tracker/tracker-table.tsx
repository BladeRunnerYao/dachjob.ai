'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { Application } from '@/lib/api/types';
import { useState } from 'react';

type BadgeVariant = 'default' | 'green' | 'yellow' | 'red' | 'blue';

interface TrackerTableProps {
  applications: Application[];
  onStatusChange: (id: string, status: string) => Promise<void>;
}

const statusColors: Record<string, BadgeVariant> = {
  Saved: 'yellow',
  Applied: 'green',
  Interview: 'blue',
  Offer: 'green',
  Rejected: 'red',
};

const statusOptions = ['Saved', 'Applied', 'Interview', 'Rejected', 'Offer'];

function toPercent(score: number): number {
  return Math.round((Math.min(Math.max(score, 1), 5) / 5) * 100);
}

function formatDate(value?: string | null): string {
  return value ? new Date(value).toLocaleDateString() : '-';
}

export function TrackerTable({ applications, onStatusChange }: TrackerTableProps) {
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className="px-4 py-3 font-medium">Job Title</th>
              <th className="px-4 py-3 font-medium">Company</th>
              <th className="px-4 py-3 font-medium">Score</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Applied</th>
              <th className="px-4 py-3 font-medium">Notes</th>
              <th className="px-4 py-3 font-medium">Added</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((app) => (
              <tr key={app.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-900">{app.job_title}</td>
                <td className="px-4 py-3 text-slate-600">{app.company}</td>
                <td className="px-4 py-3">
                  {app.score != null && (() => {
                    const pct = toPercent(app.score);
                    return (
                      <Badge variant={pct >= 84 ? 'green' : pct >= 72 ? 'yellow' : 'red'}>
                        {pct}%
                      </Badge>
                    );
                  })()}
                </td>
                <td className="px-4 py-3 relative">
                  <button
                    onClick={() => setOpenDropdown(openDropdown === app.id ? null : app.id)}
                    className="focus:outline-none"
                  >
                    <Badge variant={statusColors[app.status] || 'default'}>{app.status}</Badge>
                  </button>
                  {openDropdown === app.id && (
                    <div className="absolute top-full left-0 mt-1 w-36 rounded-md border border-slate-200 bg-white shadow-lg z-10">
                      {statusOptions.map((s) => (
                        <button
                          key={s}
                          onClick={() => { void onStatusChange(app.id, s); setOpenDropdown(null); }}
                          className={`block w-full px-3 py-1.5 text-left text-xs hover:bg-slate-100 ${
                            s === app.status ? 'font-semibold text-blue-600' : 'text-slate-700'
                          }`}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-500">{formatDate(app.applied_at)}</td>
                <td className="px-4 py-3 text-slate-500 max-w-[200px] truncate">{app.notes || '-'}</td>
                <td className="px-4 py-3 text-slate-500">{formatDate(app.added_at || app.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </CardContent>
    </Card>
  );
}
