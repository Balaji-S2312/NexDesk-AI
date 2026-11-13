import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Search, X } from 'lucide-react';

export interface AdaptiveSelectOption {
  value: string;
  label: string;
  description?: string;
  icon?: React.ReactNode;
  disabled?: boolean;
}

export interface AdaptiveSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: AdaptiveSelectOption[];
  placeholder?: string;
  disabled?: boolean;
  searchable?: boolean;
  searchPlaceholder?: string;
  emptyMessage?: string;
  ariaLabel?: string;
  label?: string;
  id?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export const AdaptiveSelect: React.FC<AdaptiveSelectProps> = ({
  value,
  onChange,
  options,
  placeholder = 'Select an option',
  disabled = false,
  searchable,
  searchPlaceholder = 'Search options...',
  emptyMessage = 'No matching options found',
  ariaLabel,
  label,
  id,
  size = 'md',
  className = '',
}) => {
  const generatedId = useId();
  const controlId = id || `adaptive-select-${generatedId}`;
  const listboxId = `${controlId}-listbox`;

  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < 640 : false
  );
  const [coords, setCoords] = useState<{
    top: number;
    left: number;
    width: number;
    maxHeight: number;
    openUpward: boolean;
  }>({
    top: 0,
    left: 0,
    width: 240,
    maxHeight: 280,
    openUpward: false,
  });

  const enableSearch = searchable ?? options.length >= 7;

  const selectedOption = useMemo(
    () => options.find((opt) => opt.value === value) || null,
    [options, value]
  );

  const filteredOptions = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) return options;
    return options.filter(
      (opt) =>
        opt.label.toLowerCase().includes(query) ||
        opt.value.toLowerCase().includes(query) ||
        (opt.description && opt.description.toLowerCase().includes(query))
    );
  }, [options, searchTerm]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handleResize = () => setIsMobile(window.innerWidth < 640);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const updatePosition = () => {
    const trigger = triggerRef.current;
    if (!trigger || typeof window === 'undefined') return;
    const rect = trigger.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const openUpward = spaceBelow < 220 && spaceAbove > spaceBelow;
    const maxHeight = Math.min(280, Math.max(150, openUpward ? spaceAbove : spaceBelow));
    const desiredWidth = Math.max(rect.width, 200);
    const maxLeft = Math.max(12, window.innerWidth - desiredWidth - 12);

    setCoords({
      top: openUpward ? Math.max(12, rect.top - 6) : rect.bottom + 6,
      left: Math.min(rect.left, maxLeft),
      width: desiredWidth,
      maxHeight,
      openUpward,
    });
  };

  useEffect(() => {
    if (!open) return;

    const currentIdx = options.findIndex((opt) => opt.value === value && !opt.disabled);
    setActiveIndex(currentIdx >= 0 ? currentIdx : 0);
  }, [open, options, value]);

  useEffect(() => {
    if (!open) return;

    if (!isMobile) {
      updatePosition();
    }

    const focusTimer = setTimeout(() => {
      if (enableSearch && searchInputRef.current) {
        searchInputRef.current.focus();
      }
    }, 10);

    const handleReposition = () => {
      if (!isMobile) updatePosition();
    };
    const handleOutsideClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        triggerRef.current?.contains(target) ||
        panelRef.current?.contains(target)
      ) {
        return;
      }
      setOpen(false);
    };
    const handleKeyGlobal = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };

    window.addEventListener('resize', handleReposition);
    window.addEventListener('scroll', handleReposition, true);
    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleKeyGlobal);

    return () => {
      clearTimeout(focusTimer);
      window.removeEventListener('resize', handleReposition);
      window.removeEventListener('scroll', handleReposition, true);
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyGlobal);
    };
  }, [open, isMobile, enableSearch]);

  useEffect(() => {
    if (!open) {
      setSearchTerm('');
    }
  }, [open]);

  const selectOption = (opt: AdaptiveSelectOption) => {
    if (opt.disabled) return;
    onChange(opt.value);
    setOpen(false);
    triggerRef.current?.focus();
  };

  const moveFocus = (delta: number) => {
    if (filteredOptions.length === 0) return;
    let next = activeIndex;
    for (let i = 0; i < filteredOptions.length; i++) {
      next = (next + delta + filteredOptions.length) % filteredOptions.length;
      if (!filteredOptions[next].disabled) {
        setActiveIndex(next);
        return;
      }
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (disabled) return;

    if (!open) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        setOpen(true);
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        moveFocus(1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        moveFocus(-1);
        break;
      case 'Home':
        event.preventDefault();
        setActiveIndex(0);
        break;
      case 'End':
        event.preventDefault();
        setActiveIndex(Math.max(0, filteredOptions.length - 1));
        break;
      case 'Enter':
        event.preventDefault();
        if (activeIndex >= 0 && filteredOptions[activeIndex]) {
          selectOption(filteredOptions[activeIndex]);
        }
        break;
      case 'Tab':
        setOpen(false);
        break;
      default:
        break;
    }
  };

  const sizeClasses =
    size === 'sm'
      ? 'px-3 py-1.5 text-xs rounded-lg min-h-[34px]'
      : 'px-3 py-2 text-xs rounded-xl min-h-[38px]';

  const renderOptionsList = (touchMode: boolean) => (
    <div className="flex flex-col">
      {enableSearch && (
        <div className="p-2 border-b border-[#DCE4E3] bg-[#F7F8F6] sticky top-0 z-10">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-[#526773] absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setActiveIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              className="w-full pl-8 pr-7 py-1.5 text-xs rounded-lg border border-[#DCE4E3] bg-white text-[#172B3A] placeholder-[#526773] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B]"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#526773] hover:text-[#172B3A]"
                aria-label="Clear search"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>
      )}

      <ul
        id={listboxId}
        role="listbox"
        aria-label={ariaLabel || label || placeholder}
        className="overflow-y-auto p-1.5 space-y-0.5"
        style={{ maxHeight: touchMode ? '55vh' : `${coords.maxHeight}px` }}
      >
        {filteredOptions.length === 0 ? (
          <li className="px-3 py-4 text-center text-xs text-[#526773] select-none">
            {emptyMessage}
          </li>
        ) : (
          filteredOptions.map((opt, idx) => {
            const isSelected = opt.value === value;
            const isActive = idx === activeIndex;
            return (
              <li
                key={opt.value}
                id={`${controlId}-opt-${idx}`}
                role="option"
                aria-selected={isSelected}
                aria-disabled={opt.disabled}
                onMouseEnter={() => !opt.disabled && setActiveIndex(idx)}
                onClick={() => selectOption(opt)}
                className={`flex items-center justify-between gap-2 rounded-lg transition-colors select-none ${
                  touchMode ? 'px-3.5 py-2.5 min-h-[44px]' : 'px-2.5 py-2'
                } ${
                  opt.disabled
                    ? 'opacity-45 cursor-not-allowed text-[#526773]'
                    : isSelected
                    ? 'bg-[#DCEFF0] text-[#075C66] font-semibold cursor-pointer'
                    : isActive
                    ? 'bg-[#F7F8F6] text-[#172B3A] cursor-pointer'
                    : 'text-[#172B3A] hover:bg-[#F7F8F6] cursor-pointer'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  {opt.icon && <span className="shrink-0 flex items-center">{opt.icon}</span>}
                  <div className="min-w-0">
                    <div className="text-xs leading-snug truncate">{opt.label}</div>
                    {opt.description && (
                      <div className="text-[11px] text-[#526773] truncate">{opt.description}</div>
                    )}
                  </div>
                </div>
                {isSelected && <Check className="w-3.5 h-3.5 text-[#087E8B] shrink-0" aria-hidden="true" />}
              </li>
            );
          })
        )}
      </ul>
    </div>
  );

  const portalPanel =
    open && typeof document !== 'undefined'
      ? createPortal(
          isMobile ? (
            <div
              className="fixed inset-0 z-[140] flex items-end justify-center bg-[#172B3A]/40 backdrop-blur-[1px]"
              onMouseDown={(e) => {
                if (e.target === e.currentTarget) setOpen(false);
              }}
            >
              <div
                ref={panelRef}
                className="w-full max-w-lg bg-white rounded-t-2xl border-t border-[#DCE4E3] shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-150"
              >
                <div className="flex items-center justify-between px-4 py-3 border-b border-[#DCE4E3] bg-[#F7F8F6]">
                  <span className="text-xs font-bold text-[#172B3A] uppercase tracking-wider">
                    {label || ariaLabel || placeholder}
                  </span>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="p-1 rounded-lg text-[#526773] hover:text-[#172B3A] hover:bg-[#DCE4E3]/50"
                    aria-label="Close options"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                {renderOptionsList(true)}
              </div>
            </div>
          ) : (
            <div
              ref={panelRef}
              style={{
                position: 'fixed',
                top: coords.openUpward ? undefined : `${coords.top}px`,
                bottom: coords.openUpward ? `${window.innerHeight - coords.top}px` : undefined,
                left: `${coords.left}px`,
                width: `${coords.width}px`,
              }}
              className="z-[140] bg-white rounded-xl border border-[#DCE4E3] shadow-lg shadow-[#172B3A]/10 overflow-hidden"
            >
              {renderOptionsList(false)}
            </div>
          ),
          document.body
        )
      : null;

  return (
    <div className={`relative ${className}`}>
      <button
        ref={triggerRef}
        id={controlId}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-activedescendant={open && activeIndex >= 0 ? `${controlId}-opt-${activeIndex}` : undefined}
        aria-label={ariaLabel || label || placeholder}
        disabled={disabled}
        onClick={() => !disabled && setOpen((prev) => !prev)}
        onKeyDown={handleKeyDown}
        className={`w-full flex items-center justify-between gap-2 bg-white border text-left transition-all shadow-2xs ${sizeClasses} ${
          disabled
            ? 'bg-[#F7F8F6] border-[#DCE4E3] text-[#526773] opacity-70 cursor-not-allowed'
            : open
            ? 'border-[#087E8B] ring-2 ring-[#087E8B]/20 text-[#172B3A] cursor-pointer'
            : 'border-[#DCE4E3] hover:border-[#087E8B]/60 text-[#172B3A] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] cursor-pointer'
        }`}
      >
        <span className="flex items-center gap-2 min-w-0 flex-1">
          {selectedOption?.icon && (
            <span className="shrink-0 flex items-center">{selectedOption.icon}</span>
          )}
          <span className={`truncate font-medium ${selectedOption ? 'text-[#172B3A]' : 'text-[#526773]'}`}>
            {selectedOption ? selectedOption.label : placeholder}
          </span>
        </span>
        <ChevronDown
          className={`w-4 h-4 text-[#526773] shrink-0 transition-transform duration-150 ${
            open ? 'rotate-180 text-[#087E8B]' : ''
          }`}
          aria-hidden="true"
        />
      </button>
      {portalPanel}
    </div>
  );
};
