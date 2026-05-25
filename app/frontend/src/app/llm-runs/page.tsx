'use client';

import { useState, useEffect, useCallback, Fragment, type ChangeEvent } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api/client';
import type { LLMRun } from '@/lib/api/types';

const PAGE_SIZES = [20, 50, 100, 200];

function badgeVariant(status: string) {
  if (status === 'success' || status === 'completed') return 'green';
  if (status === 'cache_hit') return 'blue';
  if (status === 'error' || status === 'failed') return 'red';
  return 'default';
}

export default function LLMRunsPage() {
  const [runs, setRuns] = useState<LLMRun[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [taskFilter, setTaskFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<string[]>([]);

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    const params: { task?: string; status?: string; limit: number; offset: number } = {
      limit: pageSize,
      offset: page * pageSize,
    };
    if (taskFilter !== 'all') params.task = taskFilter;
    if (statusFilter !== 'all') params.status = statusFilter;

    const result = await api.getLLMRuns(params);
    setRuns(result.items);
    setTotal(result.total);
    if (tasks.length === 0) {
      const all = await api.getLLMRuns({ limit: 1 });
      setTasks([]);
    }
    setLoading(false);
  }, [taskFilter, statusFilter, page, pageSize, tasks.length]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  useEffect(() => {
    api.getLLMRuns({ limit: 200 }).then(r => {
      const t = [...new Set(r.items.map(x => x.task))];
      setTasks(t);
    });
  }, []);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handlePageSizeChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setPageSize(Number(e.target.value));
    setPage(0);
  };

  const handleTaskChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setTaskFilter(e.target.value);
    setPage(0);
  };

  const handleStatusChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setStatusFilter(e.target.value);
    setPage(0);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">LLM Runs</h1>
        <p className="text-sm text-slate-500 mt-1">{total} total runs</p>
      </div>

      <div className="flex gap-2 flex-wrap items-center">
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
          <option value="cache_hit">Cache Hit</option>
          <option value="error">Error</option>
        </select>
        <select
          value={pageSize}
          onChange={handlePageSizeChange}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs bg-white ml-auto"
        >
          {PAGE_SIZES.map(s => <option key={s} value={s}>{s} / page</option>)}
        </select>
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="px-4 py-3 font-medium">Task</th>
                <th className="px-4 py-3 font-medium">Provider</th>
                <th className="px-4 py-3 font-medium">Model</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Latency (ms)</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <Fragment key={run.id}>
                  <tr
                    onClick={() => setExpandedId(expandedId === run.id ? null : run.id)}
                    className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer"
                  >
                    <td className="px-4 py-3 font-medium text-slate-900">{run.task}</td>
                    <td className="px-4 py-3 text-slate-600">{run.provider}</td>
                    <td className="px-4 py-3 text-slate-600">{run.model}</td>
                    <td className="px-4 py-3">
                      <Badge variant={badgeVariant(run.status)}>{run.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{run.latency_ms}</td>
                    <td className="px-4 py-3 text-slate-500">{new Date(run.created_at).toLocaleString()}</td>
                  </tr>
                  {expandedId === run.id && run.error_message && (
                    <tr className="bg-red-50">
                      <td colSpan={6} className="px-4 py-3">
                        <p className="text-xs text-red-700 font-medium">Error:</p>
                        <p className="text-sm text-red-600">{run.error_message}</p>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {!loading && runs.length === 0 && (
            <p className="text-sm text-slate-500 py-8 text-center">No runs match the filters.</p>
          )}
          {loading && (
            <p className="text-sm text-slate-500 py-8 text-center">Loading...</p>
          )}
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1.5 rounded border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
          >
            Previous
          </button>
          {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => (
            <button
              key={i}
              onClick={() => setPage(i)}
              className={`px-3 py-1.5 rounded border ${i === page ? 'bg-slate-900 text-white border-slate-900' : 'border-slate-300 hover:bg-slate-50'}`}
            >
              {i + 1}
            </button>
          ))}
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="px-3 py-1.5 rounded border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
