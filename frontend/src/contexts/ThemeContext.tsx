import React, { useEffect, useState } from 'react';
import { ThemeContext, ThemePreference, ResolvedTheme } from './themeContextInstance';

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
    } catch {
      // ignore storage errors
    }
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
