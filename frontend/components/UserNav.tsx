'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { User, LogOut, ShieldCheck, ChevronDown } from 'lucide-react';

interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface UserNavProps {
  onOpenHistory?: () => void;
}

export function UserNav({ onOpenHistory }: UserNavProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  useEffect(() => {
    // Check localStorage for saved session
    const savedUser = localStorage.getItem('autopsy_user');
    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch (e) {}
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('autopsy_user');
    localStorage.removeItem('autopsy_token');
    setUser(null);
    setIsDropdownOpen(false);
  };

  if (!user) {
    return (
      <Link
        href="/login"
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/30 hover:bg-teal-500/20 hover:border-teal-500/50 transition-all shadow-sm"
      >
        <User className="w-3.5 h-3.5" />
        <span>Sign In</span>
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {onOpenHistory && (
        <button
          type="button"
          onClick={onOpenHistory}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:border-teal-500/50 hover:text-teal-600 dark:hover:text-teal-400 transition-all shadow-sm cursor-pointer"
        >
          <span className="hidden sm:inline">My History</span>
          <span className="sm:hidden">History</span>
        </button>
      )}

      <div className="relative">
        <button
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 hover:border-teal-500/50 transition-all shadow-sm"
        >
          <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-teal-500 to-emerald-400 flex items-center justify-center text-[10px] font-bold text-slate-950 uppercase shadow-inner">
            {user.name ? user.name[0] : 'U'}
          </div>
          <span className="max-w-[100px] truncate">{user.name || user.email}</span>
          <ChevronDown className="w-3 h-3 text-slate-400" />
        </button>

        {isDropdownOpen && (
          <div className="absolute right-0 mt-2 w-56 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl z-50 p-2 text-xs divide-y divide-slate-100 dark:divide-slate-800 animate-in fade-in zoom-in-95 duration-150">
            <div className="px-3 py-2">
              <p className="font-semibold text-slate-900 dark:text-white truncate">{user.name}</p>
              <p className="text-slate-500 dark:text-slate-400 text-[11px] truncate">{user.email}</p>
            </div>

            {onOpenHistory && (
              <div className="py-1">
                <button
                  onClick={() => {
                    setIsDropdownOpen(false);
                    onOpenHistory();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-left font-medium"
                >
                  <span>Audit History</span>
                </button>
              </div>
            )}

            <div className="pt-1 mt-1">
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors text-left font-medium"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
