import { getApiBase, getAuthHeaders, isBuildTime, isProduction, request } from './base-client';
import { getMockProfile } from './mocks';
import type { CandidateProfile } from './types';

export async function getProfile(): Promise<CandidateProfile> {
  try {
    return await request<CandidateProfile>('/api/profile');
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    return getMockProfile();
  }
}

export function uploadCv(rawCvMd: string): Promise<CandidateProfile> {
  return request<CandidateProfile>('/api/profile/cv', {
    method: 'POST',
    body: JSON.stringify({ raw_cv_md: rawCvMd }),
  });
}

export function importProfileFromUrl(url: string): Promise<CandidateProfile> {
  return request<CandidateProfile>('/api/profile/import-url', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export async function importProfileFromPdf(file: File): Promise<CandidateProfile> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${getApiBase()}/api/profile/import-pdf`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}
