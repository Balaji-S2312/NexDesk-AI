import React, { createContext, useContext, useEffect, useState } from 'react';

export type ThemePreference = 'light' | 'dark' | 'night' | 'auto';
export type ResolvedTheme = 'light' | 'dark' | 'night';

interface ThemeContextType {
  theme: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemePreference) => void;
  isAuto: boolean;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme] = useState<ThemePreference>('light');
  const resolvedTheme: ResolvedTheme = 'light';

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('dark', 'night');
    root.classList.add('light');
    root.setAttribute('data-theme', 'light');
    try {
      localStorage.setItem('nexdesk_theme_preference', 'light');
    } catch {}
  }, []);

  const setTheme = () => {
    // Locked to light theme per Enterprise UI guidelines
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        resolvedTheme,
        setTheme,
        isAuto: false,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
