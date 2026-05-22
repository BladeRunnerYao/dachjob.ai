'use client';

import { useState, useEffect } from 'react';
import { Fragment } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api/client';
import type { LLMRun } from '@/lib/api/types';

export default function LLMRunsPage() {
  const [runs, setRuns] = useState<LLMRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [taskFilter, setTaskFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    api.getLLMRuns().then((data) => {
      setRuns(data);
      setLoading(false);
    });
  }, []);

  const tasks = [...new Set(runs.map(r => r.task))];
  const filtered = runs.filter(r => {
    if (taskFilter !== 'all' && r.task !== taskFilter) return false;
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    return true;
  });

  if (loading) return <p className="text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">LLM Runs</h1>
        <p className="text-sm text-slate-500 mt-1">{runs.length} total runs</p>
      </div>

      <div className="flex gap-2 flex-wrap">
        <select
          value={taskFilter}
          onChange={(e) => setTaskFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs bg-white"
        >
          <option value="all">All Tasks</option>
          {tasks.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs bg-white"
        >
          <option value="all">All Statuses</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
        </select>
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="px-4 py-3 font-medium">Task</th>
                <th className="px-4 py-3 font-medium">Model</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Latency (ms)</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((run) => (
                <Fragment key={run.id}>
                  <tr
                    onClick={() => setExpandedId(expandedId === run.id ? null : run.id)}
                    className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer"
                  >
                    <td className="px-4 py-3 font-medium text-slate-900">{run.task}</td>
                    <td className="px-4 py-3 text-slate-600">{run.model}</td>
                    <td className="px-4 py-3">
                      <Badge variant={run.status === 'success' || run.status === 'completed' ? 'green' : 'red'}>{run.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{run.latency_ms}</td>
                    <td className="px-4 py-3 text-slate-500">{new Date(run.created_at).toLocaleString()}</td>
                  </tr>
                  {expandedId === run.id && run.error_message && (
                    <tr className="bg-red-50">
                      <td colSpan={5} className="px-4 py-3">
                        <p className="text-xs text-red-700 font-medium">Error:</p>
                        <p className="text-sm text-red-600">{run.error_message}</p>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="text-sm text-slate-500 py-8 text-center">No runs match the filters.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
