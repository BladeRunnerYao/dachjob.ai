'use client';

import {
  AlertTriangle,
  BriefcaseBusiness,
  CalendarDays,
  ExternalLink,
  FileText,
  Languages,
  MapPin,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import type { JobPosting } from '@/lib/api/types';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

type Section = {
  title: string;
  items: string[];
  source?: 'parsed' | 'raw' | 'computed';
};

const sectionHeadings = new Set([
  'overview',
  'job description',
  'role summary',
  'summary',
  'about you',
  'about the role',
  'about us',
  'about optiml',
  'mission',
  'tasks',
  'responsibilities',
  'your responsibilities',
  "what you'll do",
  'what you will do',
  'your tasks',
  'requirements',
  'your profile',
  'qualifications',
  'skills',
  'who we are looking for',
  'must have',
  'must-haves',
  'nice to have',
  'nice-to-have',
  'preferred qualifications',
  'benefits',
  'what we offer',
  'what this role is not',
  'the impact you will have',
  'what we look for',
  'who we are',
  'your skills',
  'why work with us',
  'diversity is our culture',
  'seniority level',
  'employment type',
  'job function',
  'industries',
  'about databricks',
  'compliance',
  'aufgaben',
  'anforderungen',
  'profil',
  'was du mitbringst',
  'was wir bieten',
]);

const listLikeSections = new Set([
  'tasks',
  'responsibilities',
  'your responsibilities',
  "what you'll do",
  'what you will do',
  'your tasks',
  'requirements',
  'your profile',
  'qualifications',
  'skills',
  'who we are looking for',
  'must have',
  'must-haves',
  'nice to have',
  'nice-to-have',
  'preferred qualifications',
  'benefits',
  'what we offer',
  'what this role is not',
  'the impact you will have',
  'what we look for',
  'your skills',
  'why work with us',
  'aufgaben',
  'anforderungen',
  'profil',
  'was du mitbringst',
  'was wir bieten',
]);

type WorkAuthorizationSignal = {
  label: string;
  detail: string;
  evidence?: string;
  severity: 'warning' | 'critical';
};

type WorkAuthorizationJson = {
  status?: string;
  label?: string;
  detail?: string;
  evidence?: string;
};

function normalizeLine(line: string) {
  return line.replace(/\s+/g, ' ').trim();
}

const inlineSectionHeadings = [
  'Who we are\\?',
  'Your responsibilities',
  'Your skills',
  'Why work with us\\?',
  'Diversity is our culture\\.',
  'Seniority level',
  'Employment type',
  'Job function',
  'Industries',
];

function exposeInlineHeadings(raw: string) {
  let expanded = raw.replace(/\r\n?/g, '\n');
  for (const heading of inlineSectionHeadings) {
    expanded = expanded.replace(new RegExp(`(^|\\s+)(${heading})(?=\\s|$)`, 'gi'), '\n$2\n');
  }
  return expanded;
}

function cleanMarkdownHeading(line: string) {
  return normalizeLine(line)
    .replace(/^#{1,6}\s*/, '')
    .replace(/\*\*/g, '')
    .replace(/[?:.]$/, '')
    .trim();
}

function cleanRawText(raw: string) {
  return exposeInlineHeadings(raw)
    .split('\n')
    .map(normalizeLine)
    .filter(Boolean);
}

function isHeading(line: string) {
  const normalized = cleanMarkdownHeading(line).toLowerCase();
  return sectionHeadings.has(normalized);
}

function isBulletish(line: string) {
  return /^[-*•]\s+/.test(line) || /^\d+[.)]\s+/.test(line);
}

function stripBullet(line: string) {
  return line.replace(/^[-*•]\s+/, '').replace(/^\d+[.)]\s+/, '').trim();
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
      current = { title: cleanMarkdownHeading(line), items: [], source: 'raw' };
      continue;
    }
    current.items.push(isBulletish(line) ? stripBullet(line) : line);
  }

  pushCurrent();
  return sections.length > 0 ? sections : [{ title: 'Job Description', items: lines }];
}

function parsedRecord(job: JobPosting) {
  return (job.parsed_json || {}) as Record<string, unknown>;
}

function buildDisplaySections(job: JobPosting): Section[] {
  return parseSections(job.raw_jd);
}

function isSwissJob(job: JobPosting) {
  const text = `${job.location || ''}\n${job.raw_jd || ''}`.toLowerCase();
  return /\b(switzerland|swiss|schweiz|suisse|svizzera|zurich|zuerich|zürich|geneva|basel|bern|lausanne)\b/.test(text);
}

function textSentences(text: string) {
  return text
    .replace(/\r\n?/g, '\n')
    .split(/(?<=[.!?])\s+|\n+/)
    .map(normalizeLine)
    .filter((sentence) => sentence.length > 12);
}

function getWorkAuthorizationJson(job: JobPosting): WorkAuthorizationJson | null {
  const parsed = parsedRecord(job);
  const direct = parsed.work_authorization;
  if (direct && typeof direct === 'object') {
    return direct as WorkAuthorizationJson;
  }
  const dachSignals = parsed.dach_signals;
  if (dachSignals && typeof dachSignals === 'object') {
    const workAuth = (dachSignals as Record<string, unknown>).work_authorization;
    if (typeof workAuth === 'string' && workAuth.trim()) {
      return { label: workAuth.trim() };
    }
  }
  return null;
}

function detectSwissWorkAuthorization(job: JobPosting): WorkAuthorizationSignal | null {
  const parsedAuth = getWorkAuthorizationJson(job);
  if (parsedAuth?.label || parsedAuth?.detail || parsedAuth?.evidence) {
    return {
      label: parsedAuth.label || 'Work authorization requirement',
      detail: parsedAuth.detail || 'The posting includes an explicit work authorization signal.',
      evidence: parsedAuth.evidence,
      severity: parsedAuth.status === 'restricted' ? 'critical' : 'warning',
    };
  }

  if (!isSwissJob(job)) return null;

  const text = `${job.title}\n${job.company}\n${job.location || ''}\n${job.raw_jd || ''}`;
  const sentences = textSentences(text);
  const strictPatterns = [
    /\b(?:only|must|require[sd]?|eligible|eligibility|applicants?|candidates?)\b.{0,140}\b(?:swiss|switzerland|schweiz|eu|e\/u|efta|european union|swedish|sweden)\b.{0,140}\b(?:citizenship|citizens?|passport|work permit|right to work|work authori[sz]ation|eligible)\b/i,
    /\b(?:swiss|switzerland|schweiz|eu|e\/u|efta|european union|swedish|sweden)\b.{0,80}\b(?:citizenship|citizens?|passport holders?|work permit|right to work)\b.{0,80}\b(?:only|required|must|can't|cannot|unable|unfortunately)\b/i,
    /\b(?:valid|existing)\b.{0,60}\b(?:swiss|switzerland|schweiz|eu|efta)\b.{0,60}\b(?:work permit|work authori[sz]ation|right to work)\b/i,
    /\b(?:can't|cannot|unable to|unfortunately)\b.{0,120}\b(?:support|sponsor)\b.{0,120}\bnon[-\s]?eu\b/i,
  ];
  const sponsorshipPatterns = [
    /\b(?:no|not|unable to|cannot)\b.{0,80}\b(?:visa sponsorship|sponsor visas?|work permit sponsorship)\b/i,
    /\b(?:must|need to)\b.{0,80}\b(?:already|currently)\b.{0,80}\b(?:authorized|eligible|right to work)\b/i,
  ];

  const strictEvidence = sentences.find((sentence) => strictPatterns.some((pattern) => pattern.test(sentence)));
  if (strictEvidence) {
    return {
      label: 'Swiss/EU/EFTA eligibility restriction',
      detail: 'This Swiss job appears to restrict applicants by citizenship, permit, or existing work authorization.',
      evidence: strictEvidence,
      severity: 'critical',
    };
  }

  const sponsorshipEvidence = sentences.find((sentence) => sponsorshipPatterns.some((pattern) => pattern.test(sentence)));
  if (sponsorshipEvidence) {
    return {
      label: 'Visa sponsorship warning',
      detail: 'This Swiss job may require existing local work authorization.',
      evidence: sponsorshipEvidence,
      severity: 'warning',
    };
  }

  return null;
}

function sectionTone(title: string) {
  const lower = title.toLowerCase();
  if (lower.includes('not')) return 'border-l-red-300 bg-red-50/40';
  if (lower.includes('benefit')) return 'border-l-emerald-300 bg-emerald-50/40';
  if (lower.includes('language')) return 'border-l-cyan-300 bg-cyan-50/40';
  if (lower.includes('require') || lower.includes('must')) return 'border-l-blue-300 bg-blue-50/40';
  if (lower.includes('respons')) return 'border-l-violet-300 bg-violet-50/40';
  if (lower.includes('summary')) return 'border-l-slate-300 bg-slate-50/60';
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
  const sections = buildDisplaySections(job);
  const workAuthorizationSignal = detectSwissWorkAuthorization(job);

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-3 text-sm text-slate-700">
          <div className="flex flex-wrap gap-2">
            {job.source && <Badge variant="blue">{job.source}</Badge>}
            {job.employment_type && <Badge>{job.employment_type}</Badge>}
            {job.workplace && <Badge>{job.workplace}</Badge>}
          </div>
          {workAuthorizationSignal && (
            <div
              className={`flex gap-3 rounded-lg border p-3 ${
                workAuthorizationSignal.severity === 'critical'
                  ? 'border-red-200 bg-red-50 text-red-900'
                  : 'border-amber-200 bg-amber-50 text-amber-900'
              }`}
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="space-y-1">
                <p className="font-semibold">{workAuthorizationSignal.label}</p>
                <p>{workAuthorizationSignal.detail}</p>
                {workAuthorizationSignal.evidence && (
                  <p className="text-xs opacity-80">Evidence: {workAuthorizationSignal.evidence}</p>
                )}
              </div>
            </div>
          )}
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
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-slate-500" />
              <h3 className="text-sm font-semibold text-slate-900">Job Description</h3>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="blue" className="gap-1">
                <Sparkles className="h-3 w-3" />
                formatted raw JD
              </Badge>
              {isSwissJob(job) && (
                <Badge className="gap-1">
                  <ShieldCheck className="h-3 w-3" />
                  Swiss market
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-slate-100">
            {sections.map((section) => (
              <section key={section.title} className={`border-l-4 px-5 py-5 ${sectionTone(section.title)}`}>
                <div className="mb-3 flex items-center gap-2">
                  {section.title.toLowerCase().includes('language') && <Languages className="h-4 w-4 text-cyan-700" />}
                  <h4 className="text-sm font-semibold text-slate-950">{section.title}</h4>
                </div>
                {renderItems(section)}
              </section>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
