'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api/client';
import type { JobPosting, MatchReport, ResumeArtifact } from '@/lib/api/types';

type Tab = 'raw' | 'parsed' | 'match' | 'evidence' | 'cv';

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<JobPosting | null>(null);
  const [match, setMatch] = useState<MatchReport | null>(null);
  const [resume, setResume] = useState<ResumeArtifact | null>(null);
  const [loading, setLoading] = useState(true);
  const [matching, setMatching] = useState(false);
  const [generatingResume, setGeneratingResume] = useState(false);
  const [tab, setTab] = useState<Tab>('raw');

  useEffect(() => {
    Promise.all([
      api.getJob(id),
      api.getLatestMatchReport(id),
      api.getLatestResumeArtifact(id),
    ]).then(([j, m, r]) => {
      setJob(j);
      setMatch(m);
      setResume(r);
      setLoading(false);
    });
  }, [id]);

  if (loading) return <p className="text-sm text-slate-500">Loading...</p>;
  if (!job) return <p className="text-sm text-red-500">Job not found</p>;

  const tabs: { key: Tab; label: string }[] = [
    { key: 'raw', label: 'Raw JD' },
    { key: 'parsed', label: 'Parsed Requirements' },
    { key: 'match', label: 'Match Score' },
    { key: 'evidence', label: 'Evidence Mapping' },
    { key: 'cv', label: 'Generated CV' },
  ];

  const barColor = (val: number) => {
    if (val >= 4) return 'bg-emerald-500';
    if (val >= 3) return 'bg-amber-500';
    return 'bg-red-500';
  };

  const parsed = job.parsed_json || {};
  const skills = (
    (parsed.must_have_skills as string[] | undefined)
    || (parsed.skills as string[] | undefined)
    || job.skills?.filter((skill) => skill.category === 'must_have').map((skill) => skill.name)
    || []
  );
  const niceSkills = (
    (parsed.nice_to_have_skills as string[] | undefined)
    || job.skills?.filter((skill) => skill.category === 'nice_to_have').map((skill) => skill.name)
    || []
  );
  const responsibilities = (parsed.responsibilities as string[] | undefined) || [];
  const years = parsed.experience_years || parsed.years_exp;

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

  const generateResume = async () => {
    setGeneratingResume(true);
    try {
      const artifact = await api.createResumeArtifact(id);
      setResume(artifact);
    } finally {
      setGeneratingResume(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{job.title}</h1>
        <p className="text-sm text-slate-500">{job.company}{job.location ? ` · ${job.location}` : ''}</p>
        <div className="flex flex-wrap gap-2 mt-2">
          {job.score != null && (
            <Badge variant={job.score >= 4.2 ? 'green' : job.score >= 3.6 ? 'yellow' : 'red'}>
              Score: {job.score}
            </Badge>
          )}
          {job.recommendation && (
            <Badge variant={job.recommendation === 'apply' ? 'green' : job.recommendation === 'maybe' ? 'yellow' : 'red'}>
              {job.recommendation}
            </Badge>
          )}
          <Badge>{job.status}</Badge>
          {job.posted_at && <Badge>Posted: {new Date(job.posted_at).toLocaleDateString()}</Badge>}
          {job.employment_type && <Badge>{job.employment_type}</Badge>}
          {job.workplace && <Badge>{job.workplace}</Badge>}
        </div>
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'raw' && (
        <div className="space-y-4">
          <Card>
            <CardContent className="space-y-2 text-sm text-slate-700">
              {job.url && (
                <p>
                  <span className="font-medium text-slate-900">Source: </span>
                  <a href={job.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                    {job.source || job.url}
                  </a>
                </p>
              )}
              {job.salary_text && <p><span className="font-medium text-slate-900">Salary: </span>{job.salary_text}</p>}
              {job.source_job_id && <p><span className="font-medium text-slate-900">Source ID: </span>{job.source_job_id}</p>}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="whitespace-pre-wrap text-sm text-slate-700 font-mono leading-relaxed">
              {job.raw_jd || 'No raw JD available.'}
            </CardContent>
          </Card>
        </div>
      )}

      {tab === 'parsed' && (
        <div className="space-y-4">
          {job.parsed_json ? (
            <>
              <Card>
                <CardHeader><h3 className="text-sm font-semibold">Skills</h3></CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {skills.map((s: string) => (
                      <Badge key={s} variant="blue">{s}</Badge>
                    ))}
                    {skills.length === 0 && <p className="text-sm text-slate-500">No skills parsed yet.</p>}
                  </div>
                </CardContent>
              </Card>
              {niceSkills.length > 0 && (
                <Card>
                  <CardHeader><h3 className="text-sm font-semibold">Nice to Have</h3></CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {niceSkills.map((s: string) => (
                        <Badge key={s}>{s}</Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              <Card>
                <CardHeader><h3 className="text-sm font-semibold">Responsibilities</h3></CardHeader>
                <CardContent>
                  <ul className="list-disc list-inside space-y-1 text-sm text-slate-700">
                    {responsibilities.map((r: string, i: number) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                  {responsibilities.length === 0 && <p className="text-sm text-slate-500">No responsibilities parsed yet.</p>}
                </CardContent>
              </Card>
              {years && (
                <Card>
                  <CardHeader><h3 className="text-sm font-semibold">Years Experience Required</h3></CardHeader>
                  <CardContent>
                    <p className="text-sm text-slate-700">{String(years)}+ years</p>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-500">No parsed data available.</p>
          )}
        </div>
      )}

      {tab === 'match' && !match && (
        <Card>
          <CardContent className="flex items-center justify-between py-4">
            <div>
              <p className="text-sm font-medium text-slate-900">No match report yet</p>
              <p className="text-xs text-slate-500">The parsed job data is already cached in the database.</p>
            </div>
            <button
              onClick={runMatch}
              disabled={matching}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {matching ? 'Analyzing...' : 'Run Match'}
            </button>
          </CardContent>
        </Card>
      )}

      {tab === 'match' && match && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button
              onClick={runMatch}
              disabled={matching}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {matching ? 'Analyzing...' : 'Refresh Match'}
            </button>
          </div>
          <Card>
            <CardHeader><h3 className="text-sm font-semibold">Overall Score</h3></CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center w-24 h-24 rounded-full border-4 border-blue-600">
                  <span className="text-2xl font-bold text-blue-600">{match.overall_score}</span>
                </div>
                <div>
                  <Badge variant={match.overall_score >= 4.2 ? 'green' : match.overall_score >= 3.6 ? 'yellow' : 'red'}>
                    {match.recommendation}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><h3 className="text-sm font-semibold">Breakdown</h3></CardHeader>
            <CardContent className="space-y-3">
              {Object.entries(match.breakdown).map(([key, val]) => (
                <div key={key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-600 capitalize">{key.replace('_', ' ')}</span>
                    <span className="font-medium text-slate-900">{val}</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-200">
                    <div className={`h-2 rounded-full ${barColor(val)}`} style={{ width: `${(val / 5) * 100}%` }} />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader><h3 className="text-sm font-semibold text-emerald-700">Top Reasons</h3></CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {match.top_reasons.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                      <span className="text-emerald-500 mt-0.5">+</span>
                      {r}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><h3 className="text-sm font-semibold text-red-700">Gaps</h3></CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {match.gaps.map((g, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                      <span className="text-red-500 mt-0.5">-</span>
                      {g}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {tab === 'evidence' && (
        <Card>
          <CardContent>
            <p className="text-sm text-slate-500">Evidence mapping shows which CV evidence chunks support each requirement.</p>
            <div className="mt-4 space-y-3">
              {['Python/ML Experience', 'Kubernetes/Infrastructure', 'Team Leadership'].map((req) => (
                <div key={req} className="rounded-lg border border-slate-200 p-3">
                  <p className="text-sm font-medium text-slate-900 mb-2">{req}</p>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="green">Matched: e1, e2, e5</Badge>
                    <Badge variant="yellow">Partial: e3</Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === 'cv' && (
        <div className="space-y-4">
          <Card>
            <CardContent className="flex items-center justify-between py-4">
              <div>
                <p className="text-sm font-medium text-slate-900">Tailored Resume</p>
                <p className="text-xs text-slate-500">Auto-generated based on match analysis</p>
              </div>
              <button
                onClick={generateResume}
                disabled={generatingResume}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {generatingResume ? 'Generating...' : 'Generate CV'}
              </button>
            </CardContent>
          </Card>
          {resume?.html_url && resume.html_url !== '#' && (
            <div className="rounded-lg border border-slate-200 overflow-hidden">
              <iframe
                src={resume.html_url}
                className="w-full h-[600px]"
                title="Generated CV"
              />
            </div>
          )}
          {(!resume?.html_url || resume.html_url === '#') && (
            <div className="flex items-center justify-center h-48 rounded-lg border border-dashed border-slate-300">
              <p className="text-sm text-slate-400">Click &quot;Generate CV&quot; to preview your tailored resume</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
