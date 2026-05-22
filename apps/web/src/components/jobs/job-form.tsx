'use client';

import { useState } from 'react';

interface JobFormProps {
  onClose: () => void;
  onSave: (jd: string) => void;
}

export function JobForm({ onClose, onSave }: JobFormProps) {
  const [jd, setJd] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (jd.trim()) {
      onSave(jd);
      setJd('');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Add Job</h2>
          <button onClick={onClose} className="text-sm text-slate-500 hover:text-slate-700">Close</button>
        </div>
        <form onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Paste Job Description
          </label>
          <textarea
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            rows={12}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            placeholder="Paste the full job description here..."
          />
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!jd.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Save & Analyze
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
