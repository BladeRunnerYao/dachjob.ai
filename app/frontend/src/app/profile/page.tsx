'use client';

import { useState, useEffect } from 'react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api/client';
import type { CandidateProfile, EvidenceChunk } from '@/lib/api/types';

export default function ProfilePage() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [cvMd, setCvMd] = useState('');
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

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

  if (loading) return <p className="text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Profile Vault</h1>
        <p className="text-sm text-slate-500 mt-1">Manage your CV and evidence</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-900">CV Markdown</h2>
          </CardHeader>
          <CardContent className="space-y-4">
            <textarea
              value={cvMd}
              onChange={(e) => setCvMd(e.target.value)}
              rows={16}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none"
            />
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

          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-slate-900">Evidence Chunks ({profile?.evidence_chunks?.length || 0})</h2>
            </CardHeader>
            <CardContent className="space-y-3">
              {(profile?.evidence_chunks || []).map((chunk: EvidenceChunk) => (
                <div key={chunk.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge>{chunk.source_type}</Badge>
                    <span className="text-xs text-slate-500">{chunk.source_label}</span>
                  </div>
                  <p className="text-sm text-slate-700">{chunk.content}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
