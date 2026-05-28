'use client';

import { useEffect, useCallback } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: 'lg' | 'xl' | 'full';
}

export function Modal({ open, onClose, title, children, size = 'lg' }: ModalProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [open, handleKeyDown]);

  if (!open) return null;

  const sizeClass =
    size === 'full'
      ? 'w-[95vw] h-[95vh]'
      : size === 'xl'
        ? 'w-[90vw] max-w-5xl max-h-[90vh]'
        : 'w-[85vw] max-w-3xl max-h-[85vh]';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className={`relative ${sizeClass} bg-white rounded-xl shadow-2xl flex flex-col overflow-hidden`}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        {(title || true) && (
          <div className="flex items-center justify-between shrink-0 border-b border-slate-200 px-5 py-3">
            {title ? (
              <h2 className="text-base font-semibold text-slate-900">{title}</h2>
            ) : (
              <div />
            )}
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-auto">{children}</div>
      </div>
    </div>
  );
}
