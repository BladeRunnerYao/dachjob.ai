'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  Building2,
  CalendarDays,
  CheckCircle2,
  Download,
  ExternalLink,
  MapPin,
  Briefcase,
  Monitor,
  Clock,
  Plus,
  TrendingUp,
  Sparkles,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Modal } from '@/components/ui/modal';
import { api } from '@/lib/api/client';
import type {
  ApplicationJobStatus,
  JobPosting,
  MatchReport,
  ResumeArtifact,
  CandidateProfile,
  ResumeStyle,
} from '@/lib/api/types';

// ── Section parsing (from raw JD — fallback only) ────────────────

const RESPONSIBILITY_HEADINGS = new Set([
  'responsibilities',
  'your responsibilities',
  "what you'll do",
  'what you will do',
  'your tasks',
  'tasks',
  'the impact you will have',
  'aufgaben',
]);

const QUALIFICATION_HEADINGS = new Set([
  'requirements',
  'your profile',
  'qualifications',
  'qualification',
  'skills',
  'who we are looking for',
  'must have',
  'must-haves',
  'nice to have',
  'nice-to-have',
  'preferred qualifications',
  'what we look for',
  'your skills',
  'anforderungen',
  'profil',
  'was du mitbringst',
]);

const ALL_KNOWN_HEADINGS = new Set([
  'overview', 'job description', 'role summary', 'summary',
  'about you', 'about the role', 'about us', 'about optiml', 'mission',
  'benefits', 'what we offer', 'what this role is not',
  'who we are', 'why work with us', 'diversity is our culture',
  'seniority level', 'employment type', 'job function', 'industries',
  'about databricks', 'compliance', 'was wir bieten',
  ...RESPONSIBILITY_HEADINGS,
  ...QUALIFICATION_HEADINGS,
]);

function normalizeLine(line: string) {
  return line.replace(/\s+/g, ' ').trim();
}

function cleanMarkdownHeading(line: string) {
  return normalizeLine(line)
    .replace(/^#{1,6}\s*/, '')
    .replace(/\*\*/g, '')
    .replace(/[?:.]$/, '')
    .trim();
}

function isBulletish(line: string) {
  return /^[-*•]\s+/.test(line) || /^\d+[.)]\s+/.test(line);
}

function stripBullet(line: string) {
  return line.replace(/^[-*•]\s+/, '').replace(/^\d+[.)]\s+/, '').trim();
}

type JDSection = { title: string; items: string[] };

function parseRawJd(raw?: string): JDSection[] {
  if (!raw?.trim()) return [];

  const lines = raw
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map(normalizeLine)
    .filter(Boolean);

  const sections: JDSection[] = [];
  let current: JDSection = { title: '__untitled__', items: [] };

  const pushCurrent = () => {
    if (current.items.length > 0) {
      sections.push(current);
    }
  };

  for (const line of lines) {
    const cleaned = cleanMarkdownHeading(line).toLowerCase();
    if (ALL_KNOWN_HEADINGS.has(cleaned) || cleaned.startsWith('#')) {
      pushCurrent();
      current = {
        title: cleanMarkdownHeading(line),
        items: [],
      };
      continue;
    }
    current.items.push(isBulletish(line) ? stripBullet(line) : line);
  }

  pushCurrent();
  return sections;
}

// ── Helpers ─────────────────────────────────────────────────────

function toPercent(score?: number): number | null {
  if (score == null) return null;
  return Math.round((Math.min(Math.max(score, 1), 5) / 5) * 100);
}

function isRespHeading(title: string) {
  return RESPONSIBILITY_HEADINGS.has(title.toLowerCase());
}

function isQualHeading(title: string) {
  return QUALIFICATION_HEADINGS.has(title.toLowerCase());
}

function isRequiredHeading(title: string) {
  const lower = title.toLowerCase();
  return lower === 'requirements'
    || lower === 'must have'
    || lower === 'must-haves'
    || lower === 'your profile'
    || lower === 'qualifications'
    || lower === 'qualification'
    || lower === 'who we are looking for'
    || lower === 'what we look for'
    || lower === 'your skills'
    || lower === 'anforderungen'
    || lower === 'profil'
    || lower === 'was du mitbringst';
}

function isPreferredHeading(title: string) {
  const lower = title.toLowerCase();
  return lower === 'nice to have'
    || lower === 'nice-to-have'
    || lower === 'preferred qualifications';
}

// ── Score ring component ────────────────────────────────────────

function ScoreRing({ percent, size = 140 }: { percent: number; size?: number }) {
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  const ringColor = percent >= 80 ? '#10b981' : percent >= 60 ? '#f59e0b' : '#ef4444';
  const textColor = percent >= 80 ? 'text-emerald-600' : percent >= 60 ? 'text-amber-600' : 'text-red-600';
  const bgColor = percent >= 80 ? 'bg-emerald-50' : percent >= 60 ? 'bg-amber-50' : 'bg-red-50';
  const borderColor = percent >= 80 ? 'border-emerald-200' : percent >= 60 ? 'border-amber-200' : 'border-red-200';

  return (
    <div className={`flex flex-col items-center rounded-xl border ${borderColor} ${bgColor} p-6`}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="w-full h-full -rotate-90" viewBox={`0 0 ${size} ${size}`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#e2e8f0"
            strokeWidth={strokeWidth}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={ringColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-3xl font-bold ${textColor}`}>{percent}%</span>
          <span className="text-xs text-slate-500 mt-0.5">Match</span>
        </div>
      </div>
    </div>
  );
}

// ── Read structured lists from parsed_json ──────────────────────

function readStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((v): v is string => typeof v === 'string' && v.trim().length > 0);
  }
  return [];
}

function isSkillInProfile(skill: string, profile: CandidateProfile | null): boolean {
  if (!profile) return false;
  const text = [
    profile.raw_cv_md,
    profile.headline,
  ].join(' ').toLowerCase();
  return text.includes(skill.toLowerCase());
}

const APPLICATION_LABELS: Array<{
  key: ApplicationJobStatus;
  label: string;
  activeClass: string;
  inactiveClass: string;
}> = [
  {
    key: 'applied',
    label: 'Applied',
    activeClass: 'border-emerald-500 bg-emerald-600 text-white',
    inactiveClass: 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100',
  },
  {
    key: 'interview',
    label: 'Interview',
    activeClass: 'border-blue-500 bg-blue-600 text-white',
    inactiveClass: 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100',
  },
  {
    key: 'rejected',
    label: 'Rejected',
    activeClass: 'border-red-500 bg-red-600 text-white',
    inactiveClass: 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100',
  },
  {
    key: 'offer',
    label: 'Offer',
    activeClass: 'border-violet-500 bg-violet-600 text-white',
    inactiveClass: 'border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100',
  },
];

// ── Main page ───────────────────────────────────────────────────

export default function JobDetailClient({ jobId }: { jobId?: string } = {}) {
  const params = useParams<{ id?: string }>();
  const id = jobId || params.id;
  const [job, setJob] = useState<JobPosting | null>(null);
  const [match, setMatch] = useState<MatchReport | null>(null);
  const [resume, setResume] = useState<ResumeArtifact | null>(null);
  const [htmlBlobUrl, setHtmlBlobUrl] = useState<string | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [parsing, setParsing] = useState(false);
  const [matching, setMatching] = useState(false);
  const [generatingResume, setGeneratingResume] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [resumeStyle, setResumeStyle] = useState<ResumeStyle>('german');
  const [showCv, setShowCv] = useState(false);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [ownedSkills, setOwnedSkills] = useState<Set<string>>(new Set());
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.getJob(id),
      api.getLatestMatchReport(id),
      api.getLatestResumeArtifact(id),
      api.getProfile(),
    ]).then(([j, m, r, p]) => {
      setJob(j);
      setMatch(m);
      setResume(r);
      setProfile(p);
    }).catch(() => {
      // auth expired or network error
    }).finally(() => {
      setLoading(false);
    });
  }, [id]);

  useEffect(() => {
    const artifact = resume;
    let cancelled = false;
    const blobUrls: string[] = [];

    async function load() {
      if (!artifact) {
        await Promise.resolve();
        if (!cancelled) {
          setHtmlBlobUrl(null);
          setPdfBlobUrl(null);
        }
        return;
      }
      try {
        if (artifact.has_html) {
          const url = await api.getResumeHtmlUrl(artifact.id);
          if (cancelled) { URL.revokeObjectURL(url); return; }
          blobUrls.push(url);
          setHtmlBlobUrl(url);
        }
      } catch (err) {
        if (!cancelled) {
          setResumeError(err instanceof Error ? err.message : 'Failed to load CV');
        }
      }
      try {
        if (artifact.has_pdf) {
          const url = await api.getResumePdfUrl(artifact.id);
          if (cancelled) { URL.revokeObjectURL(url); return; }
          blobUrls.push(url);
          setPdfBlobUrl(url);
        }
      } catch {
        if (!cancelled) setPdfBlobUrl(null);
      }
    }

    load();
    return () => {
      cancelled = true;
      blobUrls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [resume]);

  if (!id) return <p className="text-sm text-red-500 p-8">Job not found</p>;
  if (loading) return <p className="text-sm text-slate-500 p-8">Loading...</p>;
  if (!job) return <p className="text-sm text-red-500 p-8">Job not found</p>;

  // ── Parsed data from backend ──────────────────────────────────
  const parsed = (job.parsed_json || {}) as Record<string, unknown>;

  // Structured fields from LLM parser (primary source)
  const parsedResponsibilities: string[] = readStringList(parsed.responsibilities);
  const parsedRequiredQuals: string[] = readStringList(parsed.required_qualifications);
  const parsedPreferredQuals: string[] = readStringList(parsed.preferred_qualifications);
  const hasStructuredSections = parsedResponsibilities.length > 0 || parsedRequiredQuals.length > 0 || parsedPreferredQuals.length > 0;

  // Fallback: parse raw_jd for sections when no structured data
  const allSections = parseRawJd(job.raw_jd);
  const respSections = allSections.filter((s) => isRespHeading(s.title));
  const qualSections = allSections.filter((s) => isQualHeading(s.title));

  // ── Skills from parsed_json ────────────────────────────────────
  const mustHaveSkills = readStringList(parsed.must_have_skills);
  const niceToHaveSkills = readStringList(parsed.nice_to_have_skills);
  const hasParsedSkills = mustHaveSkills.length > 0 || niceToHaveSkills.length > 0;

  // ── Match score ────────────────────────────────────────────────
  const matchPercent = toPercent(match?.overall_score ?? job.score);

  // ── Actions ────────────────────────────────────────────────────
  const runParse = async () => {
    setParsing(true);
    try {
      const updated = await api.parseJob(id);
      setJob(updated);
    } finally {
      setParsing(false);
    }
  };

  const runMatch = async () => {
    setMatching(true);
    try {
      const report = await api.createMatchReport(id);
      const refreshedJob = await api.getJob(id);
      setMatch(report);
      setJob(refreshedJob);
    } finally {
      setMatching(false);
    }
  };

  const toggleSkill = (skill: string) => {
    setOwnedSkills((prev) => {
      const next = new Set(prev);
      if (next.has(skill)) next.delete(skill);
      else next.add(skill);
      return next;
    });
  };

  const handleApplicationStatusChange = async (status: ApplicationJobStatus) => {
    const newStatus = job!.application_status === status ? 'new' : status;
    try {
      setStatusError(null);
      const updated = await api.updateJobStatus(id, newStatus);
      setJob(updated);
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : 'Could not update job status');
    }
  };

  const handleSavedChange = async () => {
    try {
      setStatusError(null);
      const updated = await api.updateJobStatus(id, undefined, !job!.saved);
      setJob(updated);
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : 'Could not update saved label');
    }
  };

  const generateResume = async (style: ResumeStyle = resumeStyle) => {
    setGeneratingResume(true);
    setResumeError(null);
    try {
      setResumeStyle(style);
      const confirmedSkills = Array.from(ownedSkills);
      const artifact = await api.createResumeArtifact(id, confirmedSkills, style);
      setResume(artifact);
      setShowCv(true);
    } catch (err) {
      setResumeError(err instanceof Error ? err.message : 'Failed to generate CV');
    } finally {
      setGeneratingResume(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* ── Header ──────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 leading-tight">{job.title}</h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-sm text-slate-600">
          <span className="flex items-center gap-1.5 font-medium text-slate-800">
            <Building2 className="h-4 w-4 text-slate-400" />
            {job.company}
          </span>
          {job.location && (
            <span className="flex items-center gap-1.5">
              <span className="text-slate-300">·</span>
              <MapPin className="h-3.5 w-3.5 text-slate-400" />
              {job.location}
            </span>
          )}
          {job.employment_type && (
            <span className="flex items-center gap-1.5">
              <span className="text-slate-300">·</span>
              <Briefcase className="h-3.5 w-3.5 text-slate-400" />
              {job.employment_type}
            </span>
          )}
          {job.workplace && (
            <span className="flex items-center gap-1.5">
              <span className="text-slate-300">·</span>
              <Monitor className="h-3.5 w-3.5 text-slate-400" />
              {job.workplace}
            </span>
          )}
          {job.posted_at && (
            <span className="flex items-center gap-1.5">
              <span className="text-slate-300">·</span>
              <CalendarDays className="h-3.5 w-3.5 text-slate-400" />
              Posted {new Date(job.posted_at).toLocaleDateString()}
            </span>
          )}
          {!job.parsed_json && (
            <span className="flex items-center gap-1.5">
              <span className="text-slate-300">·</span>
              <Badge variant="yellow" className="text-xs">Not parsed</Badge>
            </span>
          )}
        </div>
        {job.salary_text && (
          <p className="mt-2 text-sm text-slate-500">{job.salary_text}</p>
        )}
        <div className="flex flex-wrap gap-2 mt-3">
          <button
            onClick={handleSavedChange}
            className={`rounded-lg border px-4 py-1.5 text-sm font-medium transition-colors ${
              job.saved
                ? 'border-amber-500 bg-amber-500 text-white'
                : 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100'
            }`}
          >
            Saved
          </button>
          {APPLICATION_LABELS.map((label) => {
            const isActive = job.application_status === label.key;
            return (
              <button
                key={label.key}
                onClick={() => handleApplicationStatusChange(label.key)}
                className={`rounded-lg border px-4 py-1.5 text-sm font-medium transition-colors ${
                  isActive ? label.activeClass : label.inactiveClass
                }`}
              >
                {label.label}
              </button>
            );
          })}
        </div>
        {statusError && <p className="mt-2 text-sm text-red-600">{statusError}</p>}
      </div>

      {/* ── Two-column body ──────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* ── Left sidebar ───────────────────────────────────── */}
        <aside className="space-y-4">
          {/* Match Score */}
          {matchPercent != null ? (
            <div className="flex justify-center">
              <ScoreRing percent={matchPercent} />
            </div>
          ) : (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-6">
                <TrendingUp className="h-8 w-8 text-slate-300" />
                <p className="text-sm text-slate-500 text-center">No match score yet</p>
                <button
                  onClick={runMatch}
                  disabled={matching}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50 w-full"
                >
                  {matching ? 'Analyzing...' : 'Run Match'}
                </button>
              </CardContent>
            </Card>
          )}

          {matchPercent != null && match && (
            <div className="text-center">
              <Badge variant={match.overall_score >= 4.2 ? 'green' : match.overall_score >= 3.6 ? 'yellow' : 'red'}>
                {match.recommendation === 'apply' ? 'Recommended' : match.recommendation === 'maybe' ? 'Consider' : 'Not Recommended'}
              </Badge>
              <button
                onClick={runMatch}
                disabled={matching}
                className="mt-3 text-xs text-slate-400 hover:text-blue-600 underline"
              >
                {matching ? 'Refreshing...' : 'Refresh match'}
              </button>
            </div>
          )}

          {/* Company card */}
          <Card>
            <CardHeader>
              <h3 className="text-sm font-semibold text-slate-900">Company</h3>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p className="font-medium text-slate-800">{job.company}</p>
              {job.location && (
                <p className="flex items-center gap-1.5 text-slate-600">
                  <MapPin className="h-3.5 w-3.5 text-slate-400" />
                  {job.location}
                </p>
              )}
              {job.employment_type && (
                <p className="flex items-center gap-1.5 text-slate-600">
                  <Briefcase className="h-3.5 w-3.5 text-slate-400" />
                  {job.employment_type}
                </p>
              )}
              {job.workplace && (
                <p className="flex items-center gap-1.5 text-slate-600">
                  <Monitor className="h-3.5 w-3.5 text-slate-400" />
                  {job.workplace}
                </p>
              )}
              {job.posted_at && (
                <p className="flex items-center gap-1.5 text-slate-600">
                  <Clock className="h-3.5 w-3.5 text-slate-400" />
                  {new Date(job.posted_at).toLocaleDateString()}
                </p>
              )}
              {job.url && (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-blue-600 hover:underline pt-1"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  View original
                </a>
              )}
            </CardContent>
          </Card>

          {/* Parse / CV generation card */}
          <Card>
            <CardContent className="py-4 space-y-3">
              {!job.parsed_json && (
                <button
                  onClick={runParse}
                  disabled={parsing}
                  className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  <Sparkles className="h-4 w-4" />
                  {parsing ? 'Parsing...' : 'Parse Job Details'}
                </button>
              )}
              {job.parsed_json && !job.parsed_json.responsibilities && (
                <button
                  onClick={runParse}
                  disabled={parsing}
                  className="w-full rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm text-blue-700 hover:bg-blue-100 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  <Sparkles className="h-4 w-4" />
                  {parsing ? 'Re-parsing...' : 'Re-parse for sections'}
                </button>
              )}
              {!generatingResume && (
                <div className="grid grid-cols-1 gap-2">
                  <button
                    onClick={() => generateResume('american')}
                    className="w-full rounded-lg bg-slate-800 px-4 py-2 text-sm text-white hover:bg-slate-700 transition-colors"
                  >
                    Generate American CV
                  </button>
                  <button
                    onClick={() => generateResume('german')}
                    className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    Generate German CV
                  </button>
                </div>
              )}
              {generatingResume && (
                <button disabled className="w-full rounded-lg bg-slate-400 px-4 py-2 text-sm text-white">
                  Generating...
                </button>
              )}
              {resume && (
                <div className="space-y-2">
                  <button
                    onClick={() => setShowCv(true)}
                    className="w-full rounded-lg bg-slate-800 px-4 py-2 text-sm text-white hover:bg-slate-700 transition-colors"
                  >
                    Preview CV
                  </button>
                  <button
                    onClick={() => generateResume(resumeStyle)}
                    disabled={generatingResume}
                    className="w-full text-xs text-slate-400 hover:text-blue-600 underline"
                  >
                    Regenerate {resumeStyle === 'american' ? 'American' : 'German'} CV
                  </button>
                </div>
              )}
            </CardContent>
          </Card>

          {resumeError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-xs text-red-700">{resumeError}</p>
            </div>
          )}
        </aside>

        {/* ── Main content ───────────────────────────────────── */}
        <div className="space-y-6 min-w-0">
          {/* ── Responsibilities ─────────────────────────────── */}
          {(parsedResponsibilities.length > 0 || respSections.length > 0) && (
            <Card>
              <CardHeader>
                <h2 className="text-base font-semibold text-slate-900">Responsibilities</h2>
              </CardHeader>
              <CardContent>
                {parsedResponsibilities.length > 0 ? (
                  <ul className="space-y-2 pl-5 text-sm leading-6 text-slate-700">
                    {parsedResponsibilities.map((item, i) => (
                      <li key={i} className="list-disc pl-1">{item}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="space-y-6">
                    {respSections.map((section) => (
                      <div key={section.title}>
                        {respSections.length > 1 && (
                          <h3 className="text-sm font-medium text-slate-700 mb-2">{section.title}</h3>
                        )}
                        <ul className="space-y-2 pl-5 text-sm leading-6 text-slate-700">
                          {section.items.map((item, i) => (
                            <li key={i} className="list-disc pl-1">{item}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Fallback: no responsibilities */}
          {parsedResponsibilities.length === 0 && respSections.length === 0 && !hasStructuredSections && allSections.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-sm text-slate-400">
                No job description content available. Import a job URL or paste a job description to get started.
              </CardContent>
            </Card>
          )}

          {/* ── Qualifications ───────────────────────────────── */}
          <Card>
            <CardHeader>
              <h2 className="text-base font-semibold text-slate-900">Qualifications</h2>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Skills tags */}
              {hasParsedSkills && (
                <div className="space-y-3">
                  {mustHaveSkills.length > 0 && (() => {
                    const matchCount = profile
                      ? mustHaveSkills.filter((s) => isSkillInProfile(s, profile)).length
                      : 0;
                    const ownedCount = mustHaveSkills.filter((s) => ownedSkills.has(s)).length;
                    return (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Required Skills</h4>
                          {profile && (
                            <Badge variant="green" className="text-xs">
                              {matchCount + ownedCount}/{mustHaveSkills.length} matched
                            </Badge>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {mustHaveSkills.map((skill) => {
                            const matched = isSkillInProfile(skill, profile);
                            const owned = ownedSkills.has(skill);
                            const isActive = matched || owned;
                            return (
                              <button
                                key={skill}
                                type="button"
                                onClick={() => !matched && toggleSkill(skill)}
                                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                                  isActive
                                    ? 'border-emerald-300 bg-emerald-100 text-emerald-700'
                                    : 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 cursor-pointer'
                                }`}
                                title={
                                  matched
                                    ? 'Found in your resume'
                                    : owned
                                      ? 'Manually confirmed'
                                      : 'Click to confirm you have this skill'
                                }
                              >
                                {isActive ? (
                                  <CheckCircle2 className="h-3 w-3" />
                                ) : (
                                  <Plus className="h-3 w-3" />
                                )}
                                {skill}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}
                  {niceToHaveSkills.length > 0 && (() => {
                    const matchCount = profile
                      ? niceToHaveSkills.filter((s) => isSkillInProfile(s, profile)).length
                      : 0;
                    const ownedCount = niceToHaveSkills.filter((s) => ownedSkills.has(s)).length;
                    return (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Preferred Skills</h4>
                          {profile && (
                            <Badge variant="green" className="text-xs">
                              {matchCount + ownedCount}/{niceToHaveSkills.length} matched
                            </Badge>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {niceToHaveSkills.map((skill) => {
                            const matched = isSkillInProfile(skill, profile);
                            const owned = ownedSkills.has(skill);
                            const isActive = matched || owned;
                            return (
                              <button
                                key={skill}
                                type="button"
                                onClick={() => !matched && toggleSkill(skill)}
                                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                                  isActive
                                    ? 'border-emerald-300 bg-emerald-100 text-emerald-700'
                                    : 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 cursor-pointer'
                                }`}
                                title={
                                  matched
                                    ? 'Found in your resume'
                                    : owned
                                      ? 'Manually confirmed'
                                      : 'Click to confirm you have this skill'
                                }
                              >
                                {isActive ? (
                                  <CheckCircle2 className="h-3 w-3" />
                                ) : (
                                  <Plus className="h-3 w-3" />
                                )}
                                {skill}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}
                  {parsed.experience_years != null && (
                    <p className="text-sm text-slate-600">
                      <span className="font-medium">{String(parsed.experience_years)}+ years</span> of experience required
                    </p>
                  )}
                  {ownedSkills.size > 0 && (
                    <p className="text-xs text-slate-400">
                      {ownedSkills.size} skill{ownedSkills.size > 1 ? 's' : ''} manually confirmed — these will be emphasized in your generated CV.
                    </p>
                  )}
                </div>
              )}

              {/* Structured qualifications from LLM */}
              {parsedRequiredQuals.length > 0 && (
                <div>
                  {hasParsedSkills && <hr className="border-slate-200 mb-5" />}
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Required</h4>
                  <ul className="space-y-2 pl-5 text-sm leading-6 text-slate-700">
                    {parsedRequiredQuals.map((item, i) => (
                      <li key={i} className="list-disc pl-1">{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {parsedPreferredQuals.length > 0 && (
                <div>
                  {(hasParsedSkills || parsedRequiredQuals.length > 0) && <hr className="border-slate-200 mb-5" />}
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Preferred</h4>
                  <ul className="space-y-2 pl-5 text-sm leading-6 text-slate-700">
                    {parsedPreferredQuals.map((item, i) => (
                      <li key={i} className="list-disc pl-1">{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Fallback: qualification sections from raw JD parsing */}
              {!hasStructuredSections && qualSections.length > 0 && (
                <div className="space-y-5">
                  {hasParsedSkills && <hr className="border-slate-200" />}
                  {qualSections.map((section) => {
                    const isRequired = isRequiredHeading(section.title);
                    const isPreferred = isPreferredHeading(section.title);
                    const label = isRequired ? 'Required' : isPreferred ? 'Preferred' : undefined;

                    return (
                      <div key={section.title}>
                        {label && (
                          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{label}</h4>
                        )}
                        <ul className="space-y-2 pl-5 text-sm leading-6 text-slate-700">
                          {section.items.map((item, i) => (
                            <li key={i} className="list-disc pl-1">{item}</li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* No qualifications found */}
              {!hasParsedSkills && !hasStructuredSections && qualSections.length === 0 && (
                <p className="text-sm text-slate-400 text-center py-4">
                  No qualification details extracted yet. Click &quot;Parse Job Details&quot; to extract requirements.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Untitled / plain text sections that don't fit Resp or Qual (fallback only) */}
          {!hasStructuredSections && allSections.filter((s) =>
            s.title === '__untitled__' || (!isRespHeading(s.title) && !isQualHeading(s.title))
          ).length > 0 && (
            <Card>
              <CardHeader>
                <h2 className="text-base font-semibold text-slate-900">Job Description</h2>
              </CardHeader>
              <CardContent className="text-sm leading-6 text-slate-700 space-y-3">
                {allSections
                  .filter((s) => s.title === '__untitled__' || (!isRespHeading(s.title) && !isQualHeading(s.title)))
                  .map((section, si) =>
                    section.items.map((item, ii) => (
                      <p key={`${si}-${ii}`}>{item}</p>
                    ))
                  )}
              </CardContent>
            </Card>
          )}

          {/* ── CV Modal ──────────────────────────────────────── */}
          <Modal
            open={showCv && !!htmlBlobUrl}
            onClose={() => setShowCv(false)}
            title={`${resumeStyle === 'american' ? 'American' : 'German'} CV Preview`}
            size="xl"
          >
            <div className="flex items-center justify-end gap-2 px-5 py-2 bg-slate-50 border-b border-slate-200">
              {pdfBlobUrl && (
                <a
                  href={pdfBlobUrl}
                  download="resume.pdf"
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-100 transition-colors"
                >
                  <Download className="h-3.5 w-3.5" />
                  Download PDF
                </a>
              )}
              <button
                onClick={() => generateResume(resumeStyle)}
                disabled={generatingResume}
                className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-200 transition-colors disabled:opacity-50"
              >
                {generatingResume ? 'Regenerating...' : 'Regenerate'}
              </button>
            </div>
            <iframe
              src={htmlBlobUrl!}
              className="w-full h-full min-h-[75vh] border-0"
              title="Generated CV"
            />
          </Modal>
        </div>
      </div>
    </div>
  );
}
