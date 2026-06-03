import { isBuildTime, isProduction, request } from './base-client';
import { getMockApplications } from './mocks';
import type { Application } from './types';

function byAddedDesc(a: Application, b: Application): number {
  return new Date(b.added_at || b.created_at).getTime() - new Date(a.added_at || a.created_at).getTime();
}

export async function getApplications(status?: string): Promise<Application[]> {
  const query = status ? `?status=${encodeURIComponent(status.toLowerCase())}` : '';
  try {
    const applications = await request<Application[]>(`/api/applications${query}`);
    return applications.slice().sort(byAddedDesc);
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    return getMockApplications()
      .filter((app) => !status || app.status.toLowerCase() === status.toLowerCase())
      .sort(byAddedDesc);
  }
}

export function updateApplication(
  applicationId: string,
  updates: { status?: string; notes?: string }
): Promise<Application> {
  return request<Application>(`/api/applications/${applicationId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}
