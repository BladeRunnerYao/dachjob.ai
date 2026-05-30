import { isBuildTime, isProduction, request } from './base-client';
import { getMockApplications } from './mocks';
import type { Application } from './types';

export async function getApplications(): Promise<Application[]> {
  try {
    return await request<Application[]>('/api/applications');
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    return getMockApplications();
  }
}
