import React, { useState, useRef, useEffect } from 'react';
import { Sun, Moon, Flame, Clock, Check, ChevronDown } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { ThemePreference } from '../contexts/themeContextInstance';

const THEME_OPTIONS: Array<{
  id: ThemePreference;
  label: string;
  description: string;
  icon: React.FC<{ className?: string }>;
}> = [
  {
    id: 'light',
    label: 'Light',
    description: 'Crisp, high-contrast daylight mode',
    icon: Sun,
  },
  {
    id: 'dark',
    label: 'Dark',
    description: 'Deep navy enterprise dark mode',
    icon: Moon,
  },
  {
    id: 'night',
    label: 'Night',
    description: 'Warm charcoal low-light mode',
    icon: Flame,
  },
  {
    id: 'auto',
    label: 'Auto (Time)',
    description: 'Night (7 PM – 6 AM) • Light (daytime)',
    icon: Clock,
  },
];

export const ThemeSwitcher: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const activeOption = THEME_OPTIONS.find((opt) => opt.id === theme) || THEME_OPTIONS[0];
  const ActiveIcon = activeOption.icon;

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 night:border-[#494033] bg-white dark:bg-slate-800 night:bg-[#211E19] text-slate-700 dark:text-slate-200 night:text-[#F5EBDD] hover:bg-slate-50 dark:hover:bg-slate-700/60 night:hover:bg-[#2A261F] focus:outline-none focus:ring-2 focus:ring-blue-500 night:focus:ring-[#E5A85B] text-xs font-medium transition-colors shadow-2xs"
        title={`Current Theme: ${activeOption.label} (Click to change)`}
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <ActiveIcon className="w-4 h-4 text-amber-500 dark:text-blue-400 night:text-[#E5A85B]" />
        {!compact && <span className="hidden sm:inline">{activeOption.label}</span>}
        <ChevronDown className="w-3 h-3 text-slate-400 dark:text-slate-500 night:text-[#B5A991]" />
      </button>

      {isOpen && (
        <div
          className="absolute right-0 mt-2 w-56 rounded-xl shadow-xl border border-slate-200 dark:border-slate-700 night:border-[#494033] bg-white dark:bg-slate-800 night:bg-[#211E19] py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100"
          role="menu"
          aria-orientation="vertical"
        >
          <div className="px-3 py-1.5 border-b border-slate-100 dark:border-slate-700/60 night:border-[#2A261F]">
            <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-400 night:text-[#B5A991] uppercase tracking-wider">
              Theme Mode
            </p>
          </div>

          <div className="p-1 space-y-0.5">
            {THEME_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              const isSelected = theme === opt.id;
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => {
                    setTheme(opt.id);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-xs transition-colors ${
                    isSelected
                      ? 'bg-blue-50 dark:bg-blue-900/30 night:bg-[#2A261F] text-blue-700 dark:text-blue-300 night:text-[#E5A85B] font-semibold'
                      : 'text-slate-700 dark:text-slate-200 night:text-[#F5EBDD] hover:bg-slate-100 dark:hover:bg-slate-700/50 night:hover:bg-[#2A261F]'
                  }`}
                  role="menuitem"
                >
                  <div className="flex items-center space-x-2.5">
                    <Icon
                      className={`w-4 h-4 ${
                        isSelected
                          ? 'text-blue-600 dark:text-blue-400 night:text-[#E5A85B]'
                          : 'text-slate-400 dark:text-slate-400 night:text-[#B5A991]'
                      }`}
                    />
                    <div>
                      <div className="leading-tight">{opt.label}</div>
                      <div className="text-[10px] text-slate-400 dark:text-slate-400 night:text-[#B5A991] font-normal">
                        {opt.id === 'auto'
                          ? `Auto (${resolvedTheme === 'night' ? 'Night active' : 'Light active'})`
                          : opt.description}
                      </div>
                    </div>
                  </div>
                  {isSelected && (
                    <Check className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 night:text-[#E5A85B] shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
