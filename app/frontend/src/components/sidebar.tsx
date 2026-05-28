'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  UserCircle,
  Briefcase,
  ClipboardList,
  Activity,
  LogOut,
  X,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/profile', label: 'Profile Vault', icon: UserCircle },
  { href: '/jobs', label: 'Jobs', icon: Briefcase },
  { href: '/tracker', label: 'Tracker', icon: ClipboardList },
  { href: '/llm-runs', label: 'LLM Runs', icon: Activity },
];

interface User {
  id: string;
  email: string;
  name: string;
}

export function Sidebar({ user, isOpen, onClose }: { user: User | null; isOpen: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { logout } = useAuth();

  const handleNavClick = () => {
    onClose();
  };

  return (
    <>
      {/* Backdrop overlay — mobile only */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 w-64 flex-col bg-slate-900 text-white
          transform transition-transform duration-200 ease-in-out shadow-xl
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0 md:z-auto md:h-screen md:shadow-none
        `}
      >
        <div className="flex h-16 items-center justify-between px-6 border-b border-slate-800">
          <Link href="/" className="text-xl font-bold tracking-tight">
            dachjob.ai
          </Link>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white md:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => {
            const isActive = item.href === '/'
              ? pathname === '/'
              : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={handleNavClick}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <Icon className="h-5 w-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        {user && (
          <div className="border-t border-slate-800 px-4 py-4">
            <div className="mb-3 text-xs text-slate-400 truncate">
              <div className="font-medium text-slate-300">{user.name}</div>
              <div>{user.email}</div>
            </div>
            <button
              onClick={logout}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
