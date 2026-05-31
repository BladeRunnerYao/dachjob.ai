import { isBuildTime, isProduction, request, requestBlob } from './base-client';
import { getMockResume } from './mocks';
import { checkTaskResult, isBackgroundTaskResponse, pollTask } from './tasks';
import type { BackgroundTask, ResumeArtifact, ResumeStyle } from './types';

const RESUME_GENERATE_TIMEOUT_MS = 120_000;

type ResumeArtifactApiResponse = {
  id: string;
  job_id: string;
  html_object_key: string;
  pdf_object_key?: string | null;
  provenance_json?: unknown[];
};

export async function getResumeHtmlUrl(artifactId: string): Promise<string> {
  const blob = await requestBlob(`/api/resumes/${artifactId}/html`);
  return URL.createObjectURL(blob);
}

export async function getResumePdfUrl(artifactId: string): Promise<string> {
  const blob = await requestBlob(`/api/resumes/${artifactId}/pdf`);
  return URL.createObjectURL(blob);
}

export function toResumeArtifact(artifact: ResumeArtifactApiResponse): ResumeArtifact {
  return {
    id: artifact.id,
    job_id: artifact.job_id,
    has_html: !!artifact.html_object_key,
    has_pdf: !!artifact.pdf_object_key,
    provenance: artifact.provenance_json || [],
  };
}

export async function createResumeArtifact(
  jobId: string,
  confirmedSkills: string[] | undefined,
  workerEnabled: boolean,
  style: ResumeStyle = 'german'
): Promise<ResumeArtifact> {
  const result = await request<ResumeArtifactApiResponse | BackgroundTask>(`/api/jobs/${jobId}/resume`, {
    method: 'POST',
    body: JSON.stringify({ confirmed_skills: confirmedSkills || [], style }),
    timeoutMs: workerEnabled ? undefined : RESUME_GENERATE_TIMEOUT_MS,
  });
  if (isBackgroundTaskResponse(result)) {
    const task = await pollTask(result.id);
    checkTaskResult(task);
    const latest = await getLatestResumeArtifact(jobId);
    if (!latest) throw new Error('Resume generation completed but no artifact found');
    return latest;
  }
  return toResumeArtifact(result);
}

export async function getLatestResumeArtifact(jobId: string): Promise<ResumeArtifact | null> {
  try {
    const artifact = await request<ResumeArtifactApiResponse | null>(`/api/jobs/${jobId}/resume`);
    return artifact ? toResumeArtifact(artifact) : null;
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    return null;
  }
}

export async function getResumeArtifact(jobId: string): Promise<ResumeArtifact> {
  const cached = await getLatestResumeArtifact(jobId);
  if (cached) return cached;
  if (isProduction()) throw new Error('Resume artifact not found');
  return getMockResume(jobId);
}
