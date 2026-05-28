'use client';

import { useState } from 'react';

interface JobFormProps {
  onClose: () => void;
  onSave: (urlText: string) => void;
  saving?: boolean;
  error?: string | null;
}

export function JobForm({ onClose, onSave, saving = false, error }: JobFormProps) {
  const [urlText, setUrlText] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (urlText.trim() && !saving) {
      onSave(urlText);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg sm:max-w-2xl mx-4 rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Add Job</h2>
          <button onClick={onClose} disabled={saving} className="text-sm text-slate-500 hover:text-slate-700 disabled:opacity-50">Close</button>
        </div>
        <form onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Job URLs
          </label>
          <textarea
            value={urlText}
            onChange={(e) => setUrlText(e.target.value)}
            rows={8}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            placeholder="https://www.linkedin.com/jobs/view/4414035441/"
          />
          {error && (
            <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 whitespace-pre-line">{error}</p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!urlText.trim() || saving}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Importing...' : 'Import Jobs'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
