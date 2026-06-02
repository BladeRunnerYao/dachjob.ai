import {
  getMockApplications,
  getMockJobs,
  getMockLLMRuns,
  getMockMatchReport,
  getMockProfile,
  getMockResume,
} from './mocks';
import { fetchTask, initWorkerMode, listTasks } from './tasks';
import * as applicationsApi from './applications';
import * as jobsApi from './jobs';
import * as llmRunsApi from './llm-runs';
import * as matchingApi from './matching';
import * as profilesApi from './profiles';
import * as resumesApi from './resumes';
import type {
  Application,
  BackgroundTask,
  CandidateProfile,
  JobImportResponse,
  JobPosting,
  JobFilterOptions,
  JobQueryOptions,
  LLMRun,
  MatchReport,
  PaginatedJobs,
  PaginatedLLMRuns,
  ResumeArtifact,
  JobFilterStatus,
  JobStatus,
  ResumeStyle,
} from './types';

export class ApiClient {
  workerEnabled = false;

  async init(): Promise<void> {
    this.workerEnabled = await initWorkerMode();
  }

  getTask(taskId: string): Promise<BackgroundTask> {
    return fetchTask(taskId);
  }

  listTasks(params?: { status?: string; kind?: string; limit?: number; offset?: number }) {
    return listTasks(params);
  }

  getResumeHtmlUrl(artifactId: string): Promise<string> {
    return resumesApi.getResumeHtmlUrl(artifactId);
  }

  getResumePdfUrl(artifactId: string): Promise<string> {
    return resumesApi.getResumePdfUrl(artifactId);
  }

  getJobs(limit?: number, offset?: number, options?: JobFilterStatus | JobQueryOptions): Promise<JobPosting[]> {
    return jobsApi.getJobs(limit, offset, options);
  }

  getJobsPaginated(limit: number, offset: number, options?: JobFilterStatus | JobQueryOptions): Promise<PaginatedJobs> {
    return jobsApi.getJobsPaginated(limit, offset, options);
  }

  getJobFilters(): Promise<JobFilterOptions> {
    return jobsApi.getJobFilters();
  }

  getJob(id: string): Promise<JobPosting> {
    return jobsApi.getJob(id);
  }

  createJob(rawJd: string): Promise<JobPosting> {
    return jobsApi.createJob(rawJd);
  }

  updateJobStatus(jobId: string, status?: JobStatus, saved?: boolean): Promise<JobPosting> {
    return jobsApi.updateJobStatus(jobId, status, saved);
  }

  parseJob(jobId: string): Promise<JobPosting> {
    return jobsApi.parseJob(jobId);
  }

  importJobs(urlText: string): Promise<JobImportResponse> {
    return jobsApi.importJobs(urlText);
  }

  getApplications(): Promise<Application[]> {
    return applicationsApi.getApplications();
  }

  updateApplication(applicationId: string, updates: { status?: string; notes?: string }): Promise<Application> {
    return applicationsApi.updateApplication(applicationId, updates);
  }

  getProfile(): Promise<CandidateProfile> {
    return profilesApi.getProfile();
  }

  uploadCv(rawCvMd: string): Promise<CandidateProfile> {
    return profilesApi.uploadCv(rawCvMd);
  }

  importProfileFromUrl(url: string): Promise<CandidateProfile> {
    return profilesApi.importProfileFromUrl(url);
  }

  importProfileFromPdf(file: File): Promise<CandidateProfile> {
    return profilesApi.importProfileFromPdf(file);
  }

  getLatestMatchReport(jobId: string): Promise<MatchReport | null> {
    return matchingApi.getLatestMatchReport(jobId);
  }

  createMatchReport(jobId: string): Promise<MatchReport> {
    return matchingApi.createMatchReport(jobId);
  }

  getMatchReport(jobId: string): Promise<MatchReport> {
    return matchingApi.getMatchReport(jobId);
  }

  createResumeArtifact(jobId: string, confirmedSkills?: string[], style?: ResumeStyle): Promise<ResumeArtifact> {
    return resumesApi.createResumeArtifact(jobId, confirmedSkills, this.workerEnabled, style);
  }

  getLatestResumeArtifact(jobId: string): Promise<ResumeArtifact | null> {
    return resumesApi.getLatestResumeArtifact(jobId);
  }

  getResumeArtifact(jobId: string): Promise<ResumeArtifact> {
    return resumesApi.getResumeArtifact(jobId);
  }

  getLLMRuns(params?: { task?: string; status?: string; limit?: number; offset?: number }): Promise<PaginatedLLMRuns> {
    return llmRunsApi.getLLMRuns(params);
  }

  getMockJobs(): JobPosting[] {
    return getMockJobs();
  }

  getMockApplications(): Application[] {
    return getMockApplications();
  }

  getMockLLMRuns(): LLMRun[] {
    return getMockLLMRuns();
  }

  getMockProfile(): CandidateProfile {
    return getMockProfile();
  }

  getMockMatchReport(jobId: string): MatchReport {
    return getMockMatchReport(jobId);
  }

  getMockResume(jobId: string): ResumeArtifact {
    return getMockResume(jobId);
  }
}

export const api = new ApiClient();
