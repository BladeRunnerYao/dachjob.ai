'use client';

import { BriefcaseBusiness, CalendarDays, ExternalLink, FileText, MapPin } from 'lucide-react';
import type { JobPosting } from '@/lib/api/types';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

type Section = {
  title: string;
  items: string[];
};

const sectionHeadings = new Set([
  'about you',
  'about the role',
  'about us',
  'about optiml',
  'mission',
  'tasks',
  'responsibilities',
  'requirements',
  'who we are looking for',
  'must have',
  'nice to have',
  'benefits',
  'what this role is not',
  'the impact you will have',
  'what we look for',
  'about databricks',
  'compliance',
]);

const listLikeSections = new Set([
  'tasks',
  'responsibilities',
  'requirements',
  'who we are looking for',
  'must have',
  'nice to have',
  'benefits',
  'what this role is not',
  'the impact you will have',
  'what we look for',
]);

const linkedinNoise = [
  'Use AI to assess how you fit',
  'Get AI-powered advice on this job',
  'Am I a good fit for this job?',
  'Tailor my resume',
  'Sign in to access',
  'Email or phone',
  'Password',
  'Forgot password?',
  'Sign in with Email',
  'New to LinkedIn?',
  'By clicking Continue',
  'Show more Show less',
  'Join now',
  'Sign in',
  'Show',
  'or',
];

function normalizeLine(line: string) {
  return line.replace(/\s+/g, ' ').trim();
}

function isNoise(line: string) {
  const lower = line.toLowerCase();
  return linkedinNoise.some((noise) => {
    const normalizedNoise = noise.toLowerCase();
    const shouldMatchExactly = normalizedNoise.length <= 8 || ['sign in', 'password'].includes(normalizedNoise);
    return shouldMatchExactly ? lower === normalizedNoise : lower.includes(normalizedNoise);
  });
}

function cleanRawText(raw: string) {
  const lines = raw
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map(normalizeLine)
    .filter(Boolean);

  return lines.filter((line) => !isNoise(line));
}

function isHeading(line: string) {
  const normalized = line.toLowerCase().replace(/:$/, '');
  return sectionHeadings.has(normalized);
}

function isBulletish(line: string) {
  return /^[-*•]\s+/.test(line);
}

function parseSections(raw?: string): Section[] {
  if (!raw?.trim()) {
    return [{ title: 'Job Description', items: ['No raw JD available.'] }];
  }

  const lines = cleanRawText(raw);
  const sections: Section[] = [];
  let current: Section = { title: 'Overview', items: [] };

  const pushCurrent = () => {
    if (current.items.length > 0) {
      sections.push(current);
    }
  };

  for (const line of lines) {
    if (isHeading(line)) {
      pushCurrent();
      current = { title: line.replace(/:$/, ''), items: [] };
      continue;
    }
    current.items.push(isBulletish(line) ? line.replace(/^[-*•]\s+/, '') : line);
  }

  pushCurrent();
  return sections.length > 0 ? sections : [{ title: 'Job Description', items: lines }];
}

function sectionTone(title: string) {
  const lower = title.toLowerCase();
  if (lower.includes('not')) return 'border-l-red-300 bg-red-50/40';
  if (lower.includes('benefit')) return 'border-l-emerald-300 bg-emerald-50/40';
  if (lower.includes('require') || lower.includes('must')) return 'border-l-blue-300 bg-blue-50/40';
  return 'border-l-slate-200 bg-white';
}

function renderItems(section: Section) {
  const listMode = listLikeSections.has(section.title.toLowerCase());

  if (listMode) {
    return (
      <ul className="space-y-2 pl-5 text-sm leading-6 text-slate-700">
        {section.items.map((item, index) => (
          <li key={`${section.title}-${index}`} className="list-disc pl-1">
            {item}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-3 text-sm leading-6 text-slate-700">
      {section.items.map((item, index) => (
        <p key={`${section.title}-${index}`}>{item}</p>
      ))}
    </div>
  );
}

export function JobDescriptionView({ job }: { job: JobPosting }) {
  const sections = parseSections(job.raw_jd);

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-3 text-sm text-slate-700">
          <div className="flex flex-wrap gap-2">
            {job.source && <Badge variant="blue">{job.source}</Badge>}
            {job.employment_type && <Badge>{job.employment_type}</Badge>}
            {job.workplace && <Badge>{job.workplace}</Badge>}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {job.url && (
              <a href={job.url} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-blue-600 hover:underline">
                <ExternalLink className="h-4 w-4" />
                Source job post
              </a>
            )}
            {job.location && (
              <span className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-slate-400" />
                {job.location}
              </span>
            )}
            {job.posted_at && (
              <span className="flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-slate-400" />
                Posted {new Date(job.posted_at).toLocaleDateString()}
              </span>
            )}
            {job.source_job_id && (
              <span className="flex items-center gap-2">
                <BriefcaseBusiness className="h-4 w-4 text-slate-400" />
                Source ID {job.source_job_id}
              </span>
            )}
          </div>
          {job.salary_text && (
            <p>
              <span className="font-medium text-slate-900">Salary: </span>
              {job.salary_text}
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader className="bg-slate-50">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">Job Description</h3>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-slate-100">
            {sections.map((section) => (
              <section key={section.title} className={`border-l-4 px-5 py-5 ${sectionTone(section.title)}`}>
                <h4 className="mb-3 text-sm font-semibold text-slate-950">{section.title}</h4>
                {renderItems(section)}
              </section>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
