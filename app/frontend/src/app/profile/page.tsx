'use client';

import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api/client';
import type { CandidateProfile } from '@/lib/api/types';

type ImportMode = 'url' | 'pdf' | 'edit';

export default function ProfilePage() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [cvMd, setCvMd] = useState('');
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [importMode, setImportMode] = useState<ImportMode>('edit');
  const [preview, setPreview] = useState(true);

  const [url, setUrl] = useState('');
  const [urlImporting, setUrlImporting] = useState(false);
  const [urlError, setUrlError] = useState('');

  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfImporting, setPdfImporting] = useState(false);
  const [pdfError, setPdfError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getProfile().then((p) => {
      setProfile(p);
      setCvMd(p.raw_cv_md);
      setLoading(false);
    });
  }, []);

  const handleSave = async () => {
    const updated = await api.uploadCv(cvMd);
    setProfile(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleUrlImport = async () => {
    if (!url.trim()) return;
    setUrlImporting(true);
    setUrlError('');
    try {
      const updated = await api.importProfileFromUrl(url.trim());
      setProfile(updated);
      setCvMd(updated.raw_cv_md);
      setUrl('');
    } catch (e) {
      setUrlError(e instanceof Error ? e.message : 'Import failed');
    } finally {
      setUrlImporting(false);
    }
  };

  const handlePdfImport = async () => {
    if (!pdfFile) return;
    setPdfImporting(true);
    setPdfError('');
    try {
      const updated = await api.importProfileFromPdf(pdfFile);
      setProfile(updated);
      setCvMd(updated.raw_cv_md);
      setPdfFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setPdfImporting(false);
    }
  };

  if (loading) return <p className="text-sm text-slate-500">Loading...</p>;

  const tabClass = (mode: ImportMode) =>
    `shrink-0 px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
      importMode === mode
        ? 'bg-white text-slate-900 border border-b-0 border-slate-300'
        : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
    }`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Profile Vault</h1>
        <p className="text-sm text-slate-500 mt-1">Import your CV from a URL, PDF, or edit directly</p>
      </div>

      <div className="flex gap-1 border-b border-slate-300 overflow-x-auto">
        <button onClick={() => setImportMode('url')} className={tabClass('url')}>
          Import from URL
        </button>
        <button onClick={() => setImportMode('pdf')} className={tabClass('pdf')}>
          Upload PDF
        </button>
        <button onClick={() => setImportMode('edit')} className={tabClass('edit')}>
          Edit Markdown
        </button>
      </div>

      {importMode === 'url' && (
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-900">Import from URL</h2>
            <p className="text-xs text-slate-500">Enter your personal website or LinkedIn profile URL</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://your-personal-site.com or https://linkedin.com/in/..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
            {urlError && <p className="text-sm text-red-600">{urlError}</p>}
            <button
              onClick={handleUrlImport}
              disabled={urlImporting || !url.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {urlImporting ? 'Importing...' : 'Import'}
            </button>
          </CardContent>
        </Card>
      )}

      {importMode === 'pdf' && (
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-900">Upload PDF Resume</h2>
            <p className="text-xs text-slate-500">Upload your CV or resume as a PDF file</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-slate-500 file:mr-4 file:rounded-lg file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
            />
            {pdfError && <p className="text-sm text-red-600">{pdfError}</p>}
            <button
              onClick={handlePdfImport}
              disabled={pdfImporting || !pdfFile}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {pdfImporting ? 'Uploading & Extracting...' : 'Upload & Extract'}
            </button>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-900">CV Markdown</h2>
              <div className="flex gap-1 rounded-lg border border-slate-300 p-0.5">
                <button
                  onClick={() => setPreview(true)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    preview ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  Preview
                </button>
                <button
                  onClick={() => setPreview(false)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    !preview ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  Edit
                </button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {preview ? (
              <div className="min-h-[400px] w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm leading-relaxed [&_h1]:text-lg [&_h1]:font-bold [&_h1]:text-slate-900 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-slate-900 [&_h2]:mt-4 [&_h2]:mb-2 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-slate-800 [&_h3]:mt-3 [&_h3]:mb-1 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1 [&_li]:text-slate-700 [&_strong]:font-semibold [&_p]:text-slate-700 [&_p]:mb-2 [&_hr]:my-4 [&_hr]:border-slate-200">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {cvMd}
                </ReactMarkdown>
              </div>
            ) : (
              <textarea
                value={cvMd}
                onChange={(e) => setCvMd(e.target.value)}
                rows={16}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none"
              />
            )}
            <div className="flex items-center gap-3">
              <button
                onClick={handleSave}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
              >
                Save CV
              </button>
              {saved && <span className="text-sm text-emerald-600">Saved!</span>}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-slate-900">Profile Summary</h2>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-xs text-slate-500">Name</p>
                <p className="text-sm font-medium text-slate-900">{profile?.full_name}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Headline</p>
                <p className="text-sm text-slate-700">{profile?.headline}</p>
              </div>
              {profile?.location && (
                <div>
                  <p className="text-xs text-slate-500">Location</p>
                  <p className="text-sm text-slate-700">{profile.location}</p>
                </div>
              )}
            </CardContent>
          </Card>

        </div>
      </div>
    </div>
  );
}
