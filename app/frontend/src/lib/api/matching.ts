import { isBuildTime, isProduction, request } from './base-client';
import { getMockMatchReport } from './mocks';
import { checkTaskResult, isBackgroundTaskResponse, pollTask } from './tasks';
import type { BackgroundTask, MatchReport } from './types';

type MatchReportApiResponse = {
  id: string;
  job_id: string;
  overall_score: number;
  recommendation: string;
  breakdown_json: Record<string, number>;
  gaps_json?: { gaps?: string[] } | null;
  explanation?: string | null;
};

export function toMatchReport(report: MatchReportApiResponse): MatchReport {
  return {
    id: report.id,
    job_id: report.job_id,
    overall_score: Number(report.overall_score),
    recommendation: report.recommendation,
    breakdown: report.breakdown_json || {},
    top_reasons: report.explanation ? [report.explanation] : [],
    gaps: report.gaps_json?.gaps || [],
    explanation: report.explanation || undefined,
  };
}

export async function getLatestMatchReport(jobId: string): Promise<MatchReport | null> {
  try {
    const report = await request<MatchReportApiResponse | null>(`/api/jobs/${jobId}/match`);
    return report ? toMatchReport(report) : null;
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    return null;
  }
}

export async function createMatchReport(jobId: string): Promise<MatchReport> {
  const result = await request<MatchReportApiResponse | BackgroundTask>(`/api/jobs/${jobId}/match`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
  if (isBackgroundTaskResponse(result)) {
    const task = await pollTask(result.id);
    checkTaskResult(task);
    const latest = await getLatestMatchReport(jobId);
    if (!latest) throw new Error('Match completed but no report found');
    return latest;
  }
  return toMatchReport(result);
}

export async function getMatchReport(jobId: string): Promise<MatchReport> {
  const cached = await getLatestMatchReport(jobId);
  if (cached) return cached;
  if (isProduction()) throw new Error('Match report not found');
  return getMockMatchReport(jobId);
}
